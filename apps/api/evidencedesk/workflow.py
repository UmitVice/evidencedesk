import json
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from evidencedesk.config import settings
from evidencedesk.db import connection
from evidencedesk.errors import DomainError, missing
from evidencedesk.models import Answer
from evidencedesk.providers import PROMPT_VERSION, Provider, provider
from evidencedesk.quotas import reserve
from evidencedesk.retrieval import search_knowledge
from evidencedesk.sessions import get_ticket


class State(TypedDict, total=False):
    ticket: dict[str, Any]
    evidence: list[dict[str, Any]]
    raw: str
    result: dict[str, Any]


def validate_response(raw: str, evidence: list[dict[str, Any]]) -> Answer:
    try:
        answer = Answer.model_validate_json(raw)
    except ValidationError as exc:
        raise DomainError(
            "invalid_model_output", "The answer failed structured validation.", 502
        ) from exc
    sources = {str(row["id"]): row for row in evidence}
    for claim in answer.claims:
        for citation in claim.citations:
            if (
                citation.source_id not in sources
                or citation.quote not in sources[citation.source_id]["body"]
            ):
                raise DomainError("invalid_citation", "The answer cited unsupported evidence.", 502)
    return answer


def read_run(owner: dict[str, Any], run_id: str) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM evidence.runs WHERE id=%s AND session_id=%s AND tenant=%s",
            (run_id, owner["id"], owner["tenant"]),
        ).fetchone()
    if not row:
        raise missing()
    return row


def analyze(
    owner: dict[str, Any], ticket_id: str, question: str, adapter: Provider | None = None
) -> dict[str, Any]:
    config, started = settings(), time.monotonic()
    if not config.ai_enabled:
        raise DomainError("ai_disabled", "Analysis is temporarily disabled.", 503)
    ticket = get_ticket(owner, ticket_id)
    adapter = adapter or provider()
    if config.ai_mode == "simulated" and question not in (
        "",
        "What should we do?",
        "Can RelayNest configure SSO?",
    ):
        raise DomainError("sample_required", "Choose a supplied sample in simulated mode.", 422)
    reserve(owner)
    with connection() as conn:
        row = conn.execute(
            "INSERT INTO evidence.runs(session_id,tenant,ticket_id,ticket_version,"
            "mode,status,question) VALUES(%s,%s,%s,%s,%s,'running',%s) RETURNING id",
            (owner["id"], owner["tenant"], ticket_id, ticket["version"], config.ai_mode, question),
        ).fetchone()
        assert row
        run_id = row["id"]
    trace: dict[str, Any] = {"prompt_version": PROMPT_VERSION, "attempts": 0, "usage": None}

    def load(_: State) -> State:
        return {"ticket": ticket}

    def retrieve(state: State) -> State:
        assert "ticket" in state
        query = question or state["ticket"]["title"]
        assert adapter
        vector = adapter.embed([query])[0]
        evidence = search_knowledge(
            owner["tenant"], query, vector, adapter.manifest, limit=config.context_limit
        )
        return {"evidence": evidence}

    def generate(state: State) -> State:
        assert "ticket" in state and "evidence" in state
        assert adapter
        if not state["evidence"]:
            return {"raw": Answer(status="insufficient_evidence", claims=[]).model_dump_json()}
        for attempt in range(2):
            if time.monotonic() - started > 26:
                raise DomainError("request_timeout", "Analysis deadline reached.", 504)
            trace["attempts"] += 1
            try:
                raw, usage = adapter.generate(state["ticket"], question, state["evidence"])
                trace["usage"] = usage
                return {"raw": raw}
            except DomainError as exc:
                if attempt or exc.code != "provider_transient" or time.monotonic() - started > 14:
                    raise
                reserve(owner, retry=True)
        raise RuntimeError("Unreachable generation state")

    def validate(state: State) -> State:
        assert "raw" in state and "evidence" in state
        return {"result": validate_response(state["raw"], state["evidence"]).model_dump()}

    def persist(state: State) -> State:
        assert "result" in state and "evidence" in state
        trace["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        with connection() as conn:
            conn.execute(
                "UPDATE evidence.runs SET status='complete',result=%s::jsonb,"
                "evidence=%s::jsonb,trace=%s::jsonb,completed_at=now() WHERE id=%s",
                (
                    json.dumps(state["result"]),
                    json.dumps(state["evidence"], default=str),
                    json.dumps(trace),
                    run_id,
                ),
            )
        return {}

    graph = StateGraph(State)
    for name, function in [
        ("load_ticket", load),
        ("retrieve_evidence", retrieve),
        ("generate_response", generate),
        ("validate_response", validate),
        ("persist_result", persist),
    ]:
        graph.add_node(name, function)
    graph.add_edge(START, "load_ticket")
    for left, right in zip(
        ["load_ticket", "retrieve_evidence", "generate_response", "validate_response"],
        ["retrieve_evidence", "generate_response", "validate_response", "persist_result"],
        strict=True,
    ):
        graph.add_edge(left, right)
    graph.add_edge("persist_result", END)
    try:
        graph.compile().invoke({}, {"recursion_limit": 8})
    except Exception as exc:
        code = exc.code if isinstance(exc, DomainError) else "analysis_failed"
        with connection() as conn:
            conn.execute(
                "UPDATE evidence.runs SET status='failed',error_code=%s,trace=%s::jsonb,"
                "completed_at=now() WHERE id=%s",
                (code, json.dumps(trace), run_id),
            )
        if isinstance(exc, DomainError):
            raise
        raise DomainError("analysis_failed", "Analysis failed safely.", 502) from exc
    return read_run(owner, str(run_id))
