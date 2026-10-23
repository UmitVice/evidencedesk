"""Build the distillation dataset: corpus -> tickets -> retrieved context -> teacher answers.

Every stage is cached as JSONL under the output directory, so a long teacher run can be
stopped and resumed. Only answers that pass EvidenceDesk's own production validators and
match the expected answer status are kept.
"""

import argparse
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from threading import Lock

from evidencedesk.errors import DomainError
from evidencedesk.models import Answer
from evidencedesk.providers import PROMPT_VERSION, answer_json_schema, build_messages
from evidencedesk.workflow import validate_response

from evidencedesk_ml.corpus import (
    Chunk,
    build_corpus,
    chunk_documents,
    load_documents,
    save_documents,
)
from evidencedesk_ml.products import PRODUCTS, Product
from evidencedesk_ml.questions import Item, build_items
from evidencedesk_ml.teacher import Teacher, TeacherError

CONTEXT_SIZE = 4
EVAL_CASES = Path(__file__).resolve().parents[2] / "apps" / "api" / "evals" / "cases.json"
WORD = re.compile(r"\w+", re.UNICODE)


def tokens(text: str) -> list[str]:
    return [w.lower() for w in WORD.findall(text)]


class BM25:
    def __init__(self, chunks: list[Chunk], k1: float = 1.4, b: float = 0.75):
        self.chunks = chunks
        self.docs = [tokens(c.title + " " + c.heading + " " + c.body) for c in chunks]
        self.avg = sum(len(d) for d in self.docs) / max(len(self.docs), 1)
        self.df = Counter(term for doc in self.docs for term in set(doc))
        self.k1, self.b = k1, b

    def score(self, query: list[str], index: int) -> float:
        doc, n = self.docs[index], len(self.docs)
        counts = Counter(doc)
        total = 0.0
        for term in set(query):
            if term not in counts:
                continue
            idf = math.log(1 + (n - self.df[term] + 0.5) / (self.df[term] + 0.5))
            tf = counts[term]
            total += idf * tf * (self.k1 + 1) / (
                tf + self.k1 * (1 - self.b + self.b * len(doc) / self.avg)
            )
        return total

    def rank(self, text: str) -> list[tuple[float, Chunk]]:
        query = tokens(text)
        scored = [(self.score(query, i), c) for i, c in enumerate(self.chunks)]
        return sorted(scored, key=lambda x: (-x[0], x[1].id))


def item_key(item: Item) -> str:
    raw = json.dumps(asdict(item), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def assemble_context(item: Item, index: BM25, rng: random.Random) -> list[Chunk]:
    ranked = index.rank(item.ticket + " " + item.question)
    context = [c for score, c in ranked if score > 0][:CONTEXT_SIZE]
    required: list[Chunk] = []
    for source in item.target_sources:
        candidates = [(s, c) for s, c in ranked if c.source_id == source]
        # Up to two passages from the target article, as hybrid retrieval would return.
        required += [c for _, c in candidates[: 1 if source == "imported-example" else 2]]
    if item.kind == "answerable" or item.kind.startswith("injection_source"):
        # Do not let an unrelated injected passage crowd out real evidence by accident.
        context = [c for c in context if c.kind != "injection" or c in required]
    keep = [c for c in context if c not in required]
    room = max(CONTEXT_SIZE - len(required), 0)
    merged = required + keep[:room]
    rng.shuffle(merged)
    return merged


def eval_ngrams(n: int = 8) -> set[tuple[str, ...]]:
    grams: set[tuple[str, ...]] = set()
    for case in json.loads(EVAL_CASES.read_text()):
        words = tokens(case["question"])
        grams |= {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}
    return grams


def contaminated(item: Item, grams: set[tuple[str, ...]], n: int = 8) -> bool:
    words = tokens(item.ticket + " " + item.question)
    return any(tuple(words[i : i + n]) in grams for i in range(len(words) - n + 1))


def check_answer(item: Item, answer: Answer, context: list[Chunk]) -> str | None:
    """Return a rejection reason, or None when the teacher answer is a valid target."""
    if answer.status != item.expected:
        return f"status_mismatch:{answer.status}"
    by_id = {c.id: c for c in context}
    cited = [by_id[cit.source_id] for claim in answer.claims for cit in claim.citations]
    if any(c.kind == "injection" for c in cited):
        return "cited_injection"
    if item.kind == "obsolete" and not any(c.status == "active" for c in cited):
        return "obsolete_without_current"
    if item.kind == "answerable" and not any(
        c.source_id in item.target_sources for c in cited
    ):
        return "missed_target_source"
    return None


def teach(
    teacher: Teacher, item: Item, context: list[Chunk]
) -> tuple[dict | None, str | None]:
    ticket = {"body": item.ticket}
    evidence = [c.evidence() for c in context]
    messages = build_messages(ticket, item.question, evidence)
    schema = answer_json_schema([c.id for c in context])
    reason = "no_attempt"
    for attempt, temperature in enumerate((0.0, 0.4)):
        try:
            raw = teacher.chat(
                messages, schema=schema, max_tokens=900, temperature=temperature,
                seed=attempt,
            )
            answer = validate_response(raw, evidence)
        except DomainError as exc:
            reason = exc.code
            continue
        except TeacherError:
            return None, "teacher_error"
        reason = check_answer(item, answer, context)
        if reason is None:
            target = answer.model_dump_json()  # canonical compact JSON as the training target
            return {
                "messages": [*messages, {"role": "assistant", "content": target}],
                "meta": {
                    "product": item.product,
                    "language": item.language,
                    "kind": item.kind,
                    "expected": item.expected,
                    "claims": len(answer.claims),
                    "context_ids": [c.id for c in context],
                    "prompt_version": PROMPT_VERSION,
                },
            }, None
    return None, reason


def stage_corpus(teacher: Teacher, out: Path, products: list[Product]) -> None:
    for product in products:
        path = out / "corpus" / f"{product.slug}.jsonl"
        if path.exists():
            continue
        docs = build_corpus(teacher, product)
        save_documents(path, docs)
        print(f"corpus {product.slug}: {len(docs)} documents", flush=True)


def stage_items(teacher: Teacher, out: Path, products: list[Product]) -> None:
    for product in products:
        path = out / "items" / f"{product.slug}.jsonl"
        if path.exists():
            continue
        docs = load_documents(out / "corpus" / f"{product.slug}.jsonl")
        items = build_items(teacher, product, docs)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(asdict(i), ensure_ascii=False) + "\n" for i in items)
        )
        print(f"items {product.slug}: {Counter(i.kind for i in items)}", flush=True)


def stage_answers(teacher: Teacher, out: Path, products: list[Product], workers: int) -> None:
    grams = eval_ngrams()
    path = out / "answers.jsonl"
    done = set()
    if path.exists():
        done = {json.loads(line)["key"] for line in path.read_text().splitlines() if line}
    jobs = []
    for product in products:
        docs = load_documents(out / "corpus" / f"{product.slug}.jsonl")
        index = BM25(chunk_documents(docs))
        for raw in (out / "items" / f"{product.slug}.jsonl").read_text().splitlines():
            item = Item(**json.loads(raw))
            key = item_key(item)
            if key in done:
                continue
            if contaminated(item, grams):
                print(f"skip contaminated {key}", flush=True)
                continue
            rng = random.Random(key)
            jobs.append((key, item, assemble_context(item, index, rng)))
    lock = Lock()
    print(f"answers: {len(jobs)} pending, {len(done)} cached", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool, path.open("a") as handle:
        futures = {pool.submit(teach, teacher, item, ctx): (key, item) for key, item, ctx in jobs}
        for count, future in enumerate(as_completed(futures), 1):
            key, item = futures[future]
            example, reason = future.result()
            record = {"key": key, "product": item.product, "kind": item.kind}
            record |= {"example": example} if example else {"rejected": reason}
            with lock:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
            if count % 25 == 0:
                print(f"answers {count}/{len(jobs)} usage={teacher.usage}", flush=True)


def rerender(example: dict) -> dict:
    """Re-render a cached example with the current build_messages() (prompt-only changes)."""
    payload = json.loads(example["messages"][1]["content"])
    evidence = [
        {
            "id": row["source_id"],
            "title": row["title"],
            "heading": row["heading"],
            "version": row["version"],
            "status": row["status"],
            "body": row["passage"],
        }
        for row in payload["evidence"]
    ]
    messages = build_messages({"body": payload["ticket"]}, payload["question"], evidence)
    return {
        "messages": [*messages, example["messages"][-1]],
        "meta": {**example["meta"], "prompt_version": PROMPT_VERSION},
    }


def stage_export(out: Path) -> dict:
    split = {p.slug: p.split for p in PRODUCTS}
    rows = [json.loads(line) for line in (out / "answers.jsonl").read_text().splitlines() if line]
    buckets: dict[str, list[dict]] = defaultdict(list)
    rejected: Counter[str] = Counter()
    for row in rows:
        if "example" in row:
            buckets[split[row["product"]]].append(rerender(row["example"]))
        else:
            rejected[row["rejected"]] += 1
    sft = out / "sft"
    sft.mkdir(parents=True, exist_ok=True)
    for name, file in (("train", "train.jsonl"), ("validation", "valid.jsonl")):
        examples = sorted(buckets[name], key=lambda x: hashlib.sha256(
            json.dumps(x["messages"], ensure_ascii=False).encode()).hexdigest())
        with (sft / file).open("w") as handle:
            for example in examples:
                handle.write(json.dumps({"messages": example["messages"]}, ensure_ascii=False))
                handle.write("\n")
        with (sft / file.replace(".jsonl", ".meta.jsonl")).open("w") as handle:
            for example in examples:
                handle.write(json.dumps(example["meta"], ensure_ascii=False) + "\n")
    report = {
        "prompt_version": PROMPT_VERSION,
        "kept": {k: len(v) for k, v in buckets.items()},
        "rejected": dict(rejected),
        "by_kind": {
            k: dict(Counter(x["meta"]["kind"] for x in v)) for k, v in buckets.items()
        },
        "by_language": {
            k: dict(Counter(x["meta"]["language"] for x in v)) for k, v in buckets.items()
        },
        "acceptance_rate": round(
            sum(len(v) for v in buckets.values()) / max(len(rows), 1), 4
        ),
    }
    (out / "build-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["corpus", "items", "answers", "export", "all"])
    parser.add_argument("--teacher-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--teacher-model", default="teacher")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--products", default="", help="Comma-separated product slugs")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    wanted = set(filter(None, args.products.split(",")))
    products = [p for p in PRODUCTS if not wanted or p.slug in wanted]
    teacher = Teacher(args.teacher_url, args.teacher_model)
    if args.stage in ("corpus", "all"):
        stage_corpus(teacher, args.out, products)
    if args.stage in ("items", "all"):
        stage_items(teacher, args.out, products)
    if args.stage in ("answers", "all"):
        stage_answers(teacher, args.out, products, args.workers)
    if args.stage in ("export", "all"):
        print(json.dumps(stage_export(args.out), indent=2))


if __name__ == "__main__":
    main()
