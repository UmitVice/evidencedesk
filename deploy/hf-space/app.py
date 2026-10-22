"""EvidenceDesk on Hugging Face ZeroGPU.

The Space runs the same Python package as the API: LangGraph analysis, production validators,
session isolation, quotas, and the approval transaction. Infrastructure is self-contained so
the demo stays free:

- PostgreSQL 16 + pgvector from `pgserver`, created fresh on every start (sandbox data only).
- bge-small embeddings computed on CPU (EMBEDDING_PROVIDER=local).
- The fine-tuned Gemma 4 12B generates on a ZeroGPU slice; each visitor spends their own
  daily GPU quota. Set SPACE_GENERATOR=openai_compatible to use a llama.cpp server instead
  (for local testing).
"""

import html
import os
import secrets
import time
from pathlib import Path
from typing import Any

import gradio as gr
import pgserver

ROOT = Path(__file__).resolve().parent
PGDATA = Path(os.environ.get("PGDATA_DIR", "/tmp/evidencedesk-pg"))
SERVER = pgserver.get_server(PGDATA, cleanup_mode="stop")
SUPERUSER_URL = SERVER.get_uri("postgres")

os.environ.update(
    {
        "ENVIRONMENT": "production",
        "AI_MODE": "live",
        "EMBEDDING_PROVIDER": "local",
        "DATABASE_URL": SUPERUSER_URL,
        "MIGRATION_DATABASE_URL": SUPERUSER_URL,
        "SERVICE_KEY": secrets.token_hex(32),
        "ANALYSIS_DEADLINE_SECONDS": os.environ.get("ANALYSIS_DEADLINE_SECONDS", "150"),
        "ATTEMPTS_PER_ENVIRONMENT_DAY": os.environ.get("ATTEMPTS_PER_ENVIRONMENT_DAY", "100"),
        "ATTEMPTS_PER_SESSION_DAY": os.environ.get("ATTEMPTS_PER_SESSION_DAY", "12"),
        "ANALYSES_PER_MINUTE": os.environ.get("ANALYSES_PER_MINUTE", "3"),
        "SESSIONS_PER_HOUR": os.environ.get("SESSIONS_PER_HOUR", "120"),
    }
)

from evidencedesk.actions import apply_approved_note, ticket_history  # noqa: E402
from evidencedesk.cli import migrate  # noqa: E402
from evidencedesk.config import settings  # noqa: E402
from evidencedesk.db import connection  # noqa: E402
from evidencedesk.errors import DomainError  # noqa: E402
from evidencedesk.live_ingest import ingest_live  # noqa: E402
from evidencedesk.providers import (  # noqa: E402
    CloudflareProvider,
    CompositeProvider,
    FallbackGenerator,
    Generator,
    LocalEmbedder,
    OpenAICompatibleGenerator,
    build_messages,
)
from evidencedesk.sessions import create_session, session  # noqa: E402
from evidencedesk.workflow import analyze  # noqa: E402

BASE_MODEL = os.environ.get("BASE_MODEL", "google/gemma-4-12B-it-qat-q4_0-unquantized")
ADAPTER_REPO = os.environ.get("ADAPTER_REPO", "")
MODEL_LABEL = ADAPTER_REPO or BASE_MODEL


def prepare_database() -> int:
    """Apply migrations, then run the app as a least-privilege runtime role."""
    settings.cache_clear()
    migrate()
    with connection(migration=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='space_runtime'").fetchone():
            conn.execute("CREATE ROLE space_runtime LOGIN IN ROLE evidencedesk_runtime")
    embedded = ingest_live(max_batches=4, allow_production=True)
    os.environ["DATABASE_URL"] = SUPERUSER_URL.replace("postgres:@", "space_runtime@", 1)
    settings.cache_clear()
    return embedded


class TransformersGenerator:
    """Fine-tuned Gemma 4 on ZeroGPU. Weights load at import time as ZeroGPU requires."""

    def __init__(self) -> None:
        import spaces
        import torch
        import transformers

        tokenizer = transformers.AutoTokenizer.from_pretrained(BASE_MODEL)
        config = transformers.AutoConfig.from_pretrained(BASE_MODEL)
        model_class = getattr(transformers, config.architectures[0])
        model = model_class.from_pretrained(BASE_MODEL, dtype=torch.bfloat16)
        if ADAPTER_REPO:
            from peft import PeftModel

            model = PeftModel.from_pretrained(model, ADAPTER_REPO).merge_and_unload()
        model.to("cuda").eval()
        self.tokenizer = tokenizer
        self.model_id = MODEL_LABEL

        @spaces.GPU(duration=75)
        def run(prompt: str) -> tuple[str, int, int]:
            inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
            with torch.inference_mode():
                output = model.generate(**inputs, max_new_tokens=700, do_sample=False)
            new = output[0, inputs["input_ids"].shape[1] :]
            text = tokenizer.decode(new, skip_special_tokens=True)
            return text, int(inputs["input_ids"].shape[1]), int(new.shape[0])

        self._run = run

    def generate(
        self, ticket: dict[str, Any], question: str, evidence: list[dict[str, Any]]
    ) -> tuple[str, dict[str, Any] | None]:
        prompt = self.tokenizer.apply_chat_template(
            build_messages(ticket, question, evidence), add_generation_prompt=True, tokenize=False
        )
        try:
            text, prompt_tokens, completion_tokens = self._run(prompt)
        except Exception as exc:  # ZeroGPU raises generic errors for quota and queue limits
            if "quota" in str(exc).lower():
                raise DomainError(
                    "provider_quota",
                    "Your free daily GPU quota is used up. Sign in to Hugging Face for more, "
                    "or try again tomorrow.",
                    429,
                ) from exc
            raise DomainError(
                "provider_transient", "The GPU worker is temporarily unavailable.", 503
            ) from exc
        usage = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
        return text.strip(), usage


def build_provider() -> CompositeProvider:
    generator: Generator
    if os.environ.get("SPACE_GENERATOR") == "openai_compatible":
        generator = OpenAICompatibleGenerator(
            os.environ["GENERATION_BASE_URL"], os.environ.get("GENERATION_MODEL", "local"),
            timeout=120,
        )
    else:
        generator = TransformersGenerator()
    if os.environ.get("CLOUDFLARE_API_TOKEN") and os.environ.get("CLOUDFLARE_ACCOUNT_ID"):
        generator = FallbackGenerator(generator, CloudflareProvider())
    return CompositeProvider(LocalEmbedder(), generator)


EMBEDDED = prepare_database()
PROVIDER = build_provider()


# ---------- rendering ----------

def esc(value: Any) -> str:
    return html.escape(str(value or ""))


def highlight(passage: str, quotes: list[str]) -> str:
    text = esc(passage)
    for quote in sorted(set(quotes), key=len, reverse=True):
        safe = esc(quote)
        if safe and safe in text:
            text = text.replace(safe, f"<mark>{safe}</mark>")
    return text


def render_answer(run: dict[str, Any]) -> tuple[str, str]:
    result = run.get("result") or {}
    evidence = run.get("evidence") or []
    by_id = {str(row["id"]): row for row in evidence}
    quotes: dict[str, list[str]] = {}
    if result.get("status") == "answered":
        parts = [
            '<div class="ed-badge ok">Answered from cited evidence</div><ol class="ed-claims">'
        ]
        for claim in result.get("claims", []):
            cites = []
            for citation in claim["citations"]:
                source = by_id.get(citation["source_id"], {})
                quotes.setdefault(citation["source_id"], []).append(citation["quote"])
                cites.append(
                    f'<li><span class="ed-src">{esc(source.get("title"))} › '
                    f'{esc(source.get("heading"))}</span><q>{esc(citation["quote"])}</q></li>'
                )
            parts.append(f"<li><p>{esc(claim['text'])}</p><ul>{''.join(cites)}</ul></li>")
        parts.append("</ol>")
        answer = "".join(parts)
    else:
        answer = (
            '<div class="ed-badge warn">Insufficient evidence: the assistant abstained</div>'
            "<p>No supplied passage supports an answer, so nothing was drafted. "
            "Escalate or ask a more specific question.</p>"
        )
    cards = []
    for index, row in enumerate(evidence, 1):
        cited = "cited" if str(row["id"]) in quotes else "not cited"
        cards.append(
            f'<details {"open" if cited == "cited" else ""}><summary>[{index}] '
            f'{esc(row.get("title"))} › {esc(row.get("heading"))} '
            f'<small>v{esc(row.get("version"))} · {esc(row.get("status"))} · {cited}</small>'
            f"</summary><p>{highlight(row['body'], quotes.get(str(row['id']), []))}</p></details>"
        )
    return answer, "".join(cards) or "<p>No passages were retrieved.</p>"


def render_history(owner: dict[str, Any], ticket_id: str) -> str:
    history = ticket_history(owner, ticket_id)
    lines = [
        f"- **{event['event']}** · {event['created_at']:%H:%M:%S} UTC"
        for event in history["audit"]
    ]
    notes = [f"> {note['content']}" for note in history["notes"]]
    if not lines and not notes:
        return "_No decisions yet for this ticket._"
    return "\n".join(["**Audit trail**", *lines, "", "**Saved notes**", *notes])


# ---------- handlers ----------

def owner_from(state: dict[str, Any]) -> dict[str, Any]:
    return session(state["token"], None)


def start(state: dict[str, Any] | None):
    created = create_session()
    owner = session(created["token"], None)
    with connection() as conn:
        tickets = conn.execute(
            "SELECT id,sample,title,body FROM evidence.tickets WHERE session_id=%s "
            "AND tenant=%s ORDER BY sample",
            (owner["id"], owner["tenant"]),
        ).fetchall()
    state = {"token": created["token"], "tickets": {t["title"]: t for t in tickets}}
    first = tickets[0]["title"]
    picker = gr.update(choices=list(state["tickets"]), value=first)
    return (state, picker, *show_ticket(state, first))


def show_ticket(state: dict[str, Any], title: str):
    ticket = state["tickets"][title]
    return f"**{esc(ticket['title'])}**\n\n{esc(ticket['body'])}", render_history(
        owner_from(state), str(ticket["id"])
    )


def run_analysis(state: dict[str, Any], title: str, question: str):
    ticket = state["tickets"][title]
    started = time.monotonic()
    try:
        run = analyze(owner_from(state), str(ticket["id"]), question.strip(), PROVIDER)
    except DomainError as exc:
        message = f'<div class="ed-badge err">{esc(exc.code)}</div><p>{esc(exc.message)}</p>'
        off = gr.update(interactive=False)
        return state, message, "", "", off, off, ""
    elapsed = time.monotonic() - started
    answer, evidence = render_answer(run)
    trace = run.get("trace") or {}
    usage = trace.get("usage") or {}
    meta = (
        f"Model `{trace.get('generation_model')}` · {elapsed:.1f} s end to end · "
        f"{usage.get('completion_tokens', '?')} output tokens · attempt {trace.get('attempts')} · "
        f"prompt `{trace.get('prompt_version')}`"
    )
    proposal = run.get("proposal")
    state = {**state, "proposal_id": str(proposal["id"]) if proposal else None}
    note = proposal["content"] if proposal else ""
    can_decide = gr.update(interactive=bool(proposal))
    return state, answer, evidence, note, can_decide, can_decide, meta


def decide(state: dict[str, Any], title: str, decision: str):
    ticket = state["tickets"][title]
    if not state.get("proposal_id"):
        return "_Run an analysis that proposes a note first._", gr.update(), gr.update()
    try:
        result = apply_approved_note(owner_from(state), state["proposal_id"], decision)
        outcome = f"**{result['status']}**" + (" (replayed)" if result["replayed"] else "")
    except DomainError as exc:
        outcome = f"**{exc.code}**: {exc.message}"
    history = render_history(owner_from(state), str(ticket["id"]))
    off = gr.update(interactive=False)
    return f"{outcome}\n\n{history}", off, off


def report_markdown() -> str:
    path = ROOT / "reports" / "model-comparison.md"
    return path.read_text() if path.exists() else "_Evaluation report not published yet._"


CSS = """
.ed-badge{display:inline-block;padding:4px 10px;border-radius:999px;font-weight:600;
  margin-bottom:8px}
.ed-badge.ok{background:#dcfce7;color:#166534}.ed-badge.warn{background:#fef9c3;color:#854d0e}
.ed-badge.err{background:#fee2e2;color:#991b1b}
.ed-claims>li{margin-bottom:12px}.ed-claims ul{list-style:none;padding-left:0;margin-top:4px}
.ed-src{font-size:.85em;opacity:.75;display:block}
q{font-style:italic}mark{background:#fde68a;padding:0 2px}
details{border:1px solid var(--border-color-primary);border-radius:8px;padding:8px 12px;
  margin:6px 0}
"""
INTRO = f"""
# EvidenceDesk
**Turn a support ticket into a reviewed internal note.** A fine-tuned Gemma 4 12B answers only
from retrieved documentation, cites verbatim quotes, abstains when evidence is missing, and can
only *propose* a note: saving it needs your explicit approval.

Generation model: `{MODEL_LABEL}` on ZeroGPU · embeddings: bge-small on CPU ·
PostgreSQL + pgvector in the Space ({EMBEDDED} passages indexed). Sandbox data resets on restart.
"""
ABOUT = (ROOT / "ABOUT.md").read_text() if (ROOT / "ABOUT.md").exists() else ""

with gr.Blocks(title="EvidenceDesk") as demo:
    state = gr.State({})
    gr.Markdown(INTRO)
    with gr.Tab("Workspace"):
        with gr.Row():
            with gr.Column(scale=2):
                ticket_pick = gr.Dropdown(label="Sample ticket", choices=[])
                ticket_view = gr.Markdown()
                question = gr.Textbox(
                    label="Agent question (optional)",
                    placeholder="Leave empty to answer the ticket itself, or ask e.g. "
                    "'Can RelayNest configure SSO?'",
                    max_length=500,
                )
                analyze_button = gr.Button("Analyze ticket", variant="primary")
                meta = gr.Markdown()
            with gr.Column(scale=3):
                gr.Markdown("### Answer")
                answer = gr.HTML()
                gr.Markdown("### Retrieved evidence")
                evidence = gr.HTML()
            with gr.Column(scale=2):
                note = gr.Textbox(label="Proposed internal note", interactive=False, lines=6)
                with gr.Row():
                    approve = gr.Button("Approve & save", variant="primary", interactive=False)
                    reject = gr.Button("Reject", interactive=False)
                history = gr.Markdown()
    with gr.Tab("Evaluation"):
        gr.Markdown(report_markdown())
    with gr.Tab("How it works"):
        gr.Markdown(ABOUT)

    demo.load(start, [state], [state, ticket_pick, ticket_view, history])
    ticket_pick.change(show_ticket, [state, ticket_pick], [ticket_view, history])
    analyze_button.click(
        run_analysis,
        [state, ticket_pick, question],
        [state, answer, evidence, note, approve, reject, meta],
        concurrency_limit=4,
    )
    decision_outputs = [history, approve, reject]
    approve.click(lambda s, t: decide(s, t, "approve"), [state, ticket_pick], decision_outputs)
    reject.click(lambda s, t: decide(s, t, "reject"), [state, ticket_pick], decision_outputs)


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=8).launch(css=CSS, theme=gr.themes.Soft())
