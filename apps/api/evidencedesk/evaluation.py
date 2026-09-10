import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from evidencedesk.config import settings
from evidencedesk.errors import DomainError
from evidencedesk.live_ingest import corpus_hash
from evidencedesk.models import Answer
from evidencedesk.providers import (
    GENERATION_MODEL,
    PROMPT_VERSION,
    CloudflareProvider,
    FixtureProvider,
)
from evidencedesk.quotas import reserve
from evidencedesk.retrieval import Mode, search_knowledge
from evidencedesk.workflow import validate_response

ROOT = Path(__file__).resolve().parents[3]
DATASET = Path(__file__).resolve().parents[1] / "evals" / "cases.json"


def retrieval_metrics(rankings: list[list[str]], labels: list[list[str]]) -> dict[str, Any]:
    recalls, reciprocal = [], []
    for ranking, relevant in zip(rankings, labels, strict=True):
        if not relevant:
            continue
        unique = list(dict.fromkeys(ranking))[:5]
        recalls.append(len(set(unique) & set(relevant)) / len(set(relevant)))
        reciprocal.append(next((1 / (i + 1) for i, doc in enumerate(unique) if doc in relevant), 0))
    n = len(recalls)
    return {
        "n": n,
        "recall_at_5": sum(recalls) / n if n else None,
        "mrr": sum(reciprocal) / n if n else None,
    }


def run_evaluation(mode: str, split: str, limit: int) -> dict[str, Any]:
    config = settings()
    if config.environment == "production":
        raise ValueError("Evaluations cannot run against production")
    database = config.database_url.get_secret_value().split("?")[0].rsplit("/", 1)[-1]
    if not database.startswith("evidencedesk_eval"):
        raise ValueError("Evaluation database name must start with evidencedesk_eval")
    dataset = json.loads(DATASET.read_text())
    selected = [case for case in dataset if split == "all" or case["split"] == split][:limit]
    adapter = CloudflareProvider() if mode == "live" else FixtureProvider()
    outcomes, labels = [], []
    modes: list[Mode] = ["lexical", "vector", "hybrid"]
    rankings: dict[str, list[list[str]]] = {method: [] for method in modes}
    for case in selected:
        outcome: dict[str, Any] = {
            "case_id": case["id"],
            "category": case["category"],
            "human_review": "pending",
            "usage": None,
            "generation_attempted": False,
            "generation_completed": False,
        }
        if case["category"] in ("approval", "provider_failure", "malformed_provider"):
            outcome.update(
                status="engineering_test_required",
                test_reference={
                    "approval": "tests/test_actions.py",
                    "provider_failure": "tests/test_rag.py",
                    "malformed_provider": "tests/test_rag.py",
                }[case["category"]],
            )
            outcomes.append(outcome)
            continue
        started = time.perf_counter()
        try:
            if mode == "live":
                reserve({"id": "evaluation"}, retry=True)
            vector = adapter.embed([case["question"]])[0]
            found = {
                method: search_knowledge(
                    "harbor",
                    case["question"],
                    vector,
                    adapter.manifest,
                    method,
                    config.candidate_limit,
                )
                for method in modes
            }
            outcome["retrieval_documents"] = {
                method: list(dict.fromkeys(row["source_id"] for row in found[method]))[:5]
                for method in modes
            }
            outcome["retrieval_misses"] = [
                method
                for method in modes
                if case["relevant_documents"]
                and not set(outcome["retrieval_documents"][method])
                & set(case["relevant_documents"])
            ]
            if case["relevant_documents"]:
                labels.append(case["relevant_documents"])
                for method in modes:
                    rankings[method].append([row["source_id"] for row in found[method]])
            if mode == "offline":
                outcome.update(
                    status="retrieval_fixture_only",
                    schema_valid=None,
                    citation_integrity=None,
                    correct_abstention=None,
                )
                outcomes.append(outcome)
                continue
            evidence = found["hybrid"][:4]
            if not evidence:
                answer = Answer(status="insufficient_evidence", claims=[])
            else:
                outcome["generation_attempted"] = True
                raw, usage = adapter.generate(
                    {"sample": case["sample"], "body": case["question"]}, case["question"], evidence
                )
                outcome["generation_completed"] = True
                answer = validate_response(raw, evidence)
                outcome["usage"] = usage
            outcome.update(
                status="evaluated",
                schema_valid=True,
                citation_integrity=True,
                correct_abstention=(answer.status == case["expected_status"]),
                answer=answer.model_dump(),
            )
        except DomainError as exc:
            outcome.update(status="failed", error_code=exc.code)
            if isinstance(exc.__cause__, ValidationError):
                outcome["validation_issues"] = [
                    {"field": list(issue["loc"]), "type": issue["type"]}
                    for issue in exc.__cause__.errors(
                        include_url=False, include_context=False, include_input=False
                    )
                ]
            outcomes.append(outcome)
            if exc.code in ("quota_exhausted", "provider_quota", "provider_unavailable"):
                break
            continue
        finally:
            if mode == "live":
                outcome["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        outcomes.append(outcome)
    durations = [outcome["elapsed_ms"] for outcome in outcomes if "elapsed_ms" in outcome]
    return {
        "mode": mode,
        "label": "Live model evaluation"
        if mode == "live"
        else "Mocked behavior checks; no live model called",
        "timestamp": datetime.now(UTC).isoformat(),
        "commit_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
        .decode()
        .strip(),
        "working_tree_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)
        ),
        "dataset_hash": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "corpus_hash": corpus_hash(),
        "prompt_version": PROMPT_VERSION,
        "embedding_manifest": adapter.manifest,
        "generation_model": GENERATION_MODEL if mode == "live" else "fixture-v1",
        "budgets": {
            "session_attempts_per_day": config.attempts_per_session_day,
            "environment_attempts_per_day": config.attempts_per_environment_day,
        },
        "retrieval": {
            "candidate_limit": config.candidate_limit,
            "rrf_k": 60,
            "cosine_distance_limit": config.cosine_distance_limit,
            "aggregation": "Unique document IDs in ranked chunk order; first five documents",
            "denominator": "Executed cases with nonempty relevant_documents labels",
        },
        "split": split,
        "dataset_counts": dict(Counter(x["category"] for x in dataset)),
        "selected_count": len(selected),
        "processed_count": len(outcomes),
        "methods": {method: retrieval_metrics(rankings[method], labels) for method in modes},
        "outcomes": outcomes,
        "human_review": "pending",
        "generation_attempts": sum(outcome["generation_attempted"] for outcome in outcomes),
        "generation_completions": sum(outcome["generation_completed"] for outcome in outcomes),
        "latency": {
            "n": len(durations),
            "measurement": "Live embedding, three retrieval methods, and optional generation; "
            "includes failures",
            "p50_ms": statistics.median(durations),
            "p95_ms": statistics.quantiles(durations, n=20, method="inclusive")[18]
            if len(durations) >= 2 else None,
        } if durations else None,
        "cost": None,
        "environment": platform.system() + "/" + platform.machine(),
        "limitations": [
            "Citation integrity does not prove semantic correctness.",
            "Offline reports measure fixture retrieval only; "
            "generation integrity is covered by tests.",
            "Control scenarios require separate real-database engineering tests.",
            "Forty scenarios are a compact regression corpus, not a market benchmark.",
        ],
    }


def write_report(report: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    name = "latest-" + report["mode"]
    (output / (name + ".json")).write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# " + report["label"],
        "",
        "Human review: pending.",
        "",
        f"Commit: `{report['commit_sha']}`",
        "",
        "| Retrieval | n | Recall@5 | MRR |",
        "| --- | --- | --- | --- |",
    ]
    for method, metrics in report["methods"].items():
        lines.append(f"| {method} | {metrics['n']} | {metrics['recall_at_5']} | {metrics['mrr']} |")
    lines += ["", *report["limitations"]]
    (output / (name + ".md")).write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["offline", "live"], default="offline")
    parser.add_argument("--split", choices=["development", "holdout", "all"], default="development")
    parser.add_argument("--limit", type=int, choices=range(1, 41), default=10)
    args = parser.parse_args()
    report = run_evaluation(args.mode, args.split, args.limit)
    write_report(report, ROOT / "reports")
    print("Report saved; live human quality review remains pending.")


if __name__ == "__main__":
    main()
