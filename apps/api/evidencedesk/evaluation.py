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
from evidencedesk.providers import PROMPT_VERSION, FixtureProvider, provider
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
    adapter = provider() if mode == "live" else FixtureProvider()
    configured_model = getattr(adapter, "model_id", "unknown")
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
                outcome["generation_model"] = getattr(adapter, "model_id", "unknown")
                outcome["usage"] = usage
                answer = validate_response(raw, evidence)
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
    generated = [outcome for outcome in outcomes if outcome["generation_completed"]]
    # Model-quality denominators exclude infrastructure failures such as quota or timeouts.
    judged = [
        outcome
        for outcome in outcomes
        if outcome.get("status") == "evaluated"
        or outcome.get("error_code")
        in ("invalid_model_output", "invalid_citation", "generation_truncated")
    ]
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
        "generation_model": configured_model,
        "served_models": dict(
            Counter(outcome.get("generation_model", "none") for outcome in generated)
        ),
        "quality": quality_metrics(judged),
        "tokens": token_totals(generated),
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
            "Forty-eight scenarios are a compact regression corpus, not a market benchmark.",
        ],
    }


def quality_metrics(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Rates over generation cases; a failed case counts against every rate it could affect."""
    n = len(outcomes)
    if not n:
        return {"n": 0}
    schema_valid = sum(
        1
        for outcome in outcomes
        if outcome.get("schema_valid")
        or (outcome.get("status") == "failed" and outcome.get("error_code") == "invalid_citation")
    )
    citation_valid = sum(1 for outcome in outcomes if outcome.get("citation_integrity"))
    abstention = sum(1 for outcome in outcomes if outcome.get("correct_abstention"))
    return {
        "n": n,
        "schema_valid_rate": round(schema_valid / n, 4),
        "citation_valid_rate": round(citation_valid / n, 4),
        "status_accuracy": round(abstention / n, 4),
        "end_to_end_pass_rate": round(
            sum(
                1
                for outcome in outcomes
                if outcome.get("citation_integrity") and outcome.get("correct_abstention")
            )
            / n,
            4,
        ),
    }


def token_totals(outcomes: list[dict[str, Any]]) -> dict[str, int]:
    totals = {"prompt_tokens": 0, "completion_tokens": 0}
    for outcome in outcomes:
        usage = outcome.get("usage") or {}
        for key in totals:
            value = usage.get(key)
            if isinstance(value, int):
                totals[key] += value
    return totals


def write_report(report: dict[str, Any], output: Path, name: str | None = None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    stem: str = name or "latest-" + report["mode"]
    (output / (stem + ".json")).write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# " + report["label"],
        "",
        "Human review: pending.",
        "",
        f"Commit: `{report['commit_sha']}`",
        "",
        f"Mode/split: {report['mode']} / {report['split']}. "
        f"Processed: {report['processed_count']}/{report['selected_count']} cases.",
        f"Prompt: `{report['prompt_version']}`. Model: `{report['generation_model']}`.",
        f"Embedding: `{report['embedding_manifest']['model']}` "
        f"({report['embedding_manifest']['dimension']} dimensions).",
        f"Dataset hash: `{report['dataset_hash']}`.",
        f"Corpus hash: `{report['corpus_hash']}`.",
        f"Generation attempts/completions: {report['generation_attempts']} / "
        f"{report['generation_completions']}.",
        "",
        "| Retrieval | n | Recall@5 | MRR |",
        "| --- | --- | --- | --- |",
    ]
    for method, metrics in report["methods"].items():
        lines.append(f"| {method} | {metrics['n']} | {metrics['recall_at_5']} | {metrics['mrr']} |")
    quality = report.get("quality") or {}
    if quality.get("n"):
        lines += [
            "",
            "| Generation | n | Schema valid | Citations valid | Status accuracy | End-to-end |",
            "| --- | --- | --- | --- | --- | --- |",
            f"| {report['generation_model']} | {quality['n']} | {quality['schema_valid_rate']} "
            f"| {quality['citation_valid_rate']} | {quality['status_accuracy']} "
            f"| {quality['end_to_end_pass_rate']} |",
            "",
            f"Served models: {report.get('served_models')}. Tokens: {report.get('tokens')}.",
        ]
    if report.get("latency"):
        timing = report["latency"]
        lines += [
            "", f"Latency n={timing['n']}: p50 {timing['p50_ms']} ms; "
            f"p95 {timing['p95_ms']} ms. {timing['measurement']}.",
        ]
    lines += ["", "## Recorded failures and disagreements", ""]
    failures = []
    for outcome in report["outcomes"]:
        if outcome["status"] == "failed":
            failures.append(f"- `{outcome['case_id']}`: `{outcome['error_code']}`.")
        elif outcome.get("correct_abstention") is False:
            failures.append(
                f"- `{outcome['case_id']}`: expected answer/abstention status disagreed."
            )
        if outcome.get("retrieval_misses"):
            failures.append(
                f"- `{outcome['case_id']}`: retrieval miss in "
                + ", ".join(outcome["retrieval_misses"]) + "."
            )
    lines += failures or [
        "No failures recorded in this run; human semantic review remains pending."
    ]
    lines += ["", *report["limitations"]]
    (output / (stem + ".md")).write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["offline", "live"], default="offline")
    parser.add_argument("--split", choices=["development", "holdout", "all"], default="development")
    parser.add_argument("--limit", type=int, choices=range(1, 49), default=10)
    parser.add_argument(
        "--name", default=None, help="Report file stem, for example compare-gemma-finetuned"
    )
    args = parser.parse_args()
    report = run_evaluation(args.mode, args.split, args.limit)
    write_report(report, ROOT / "reports", args.name)
    print("Report saved; live human quality review remains pending.")


if __name__ == "__main__":
    main()
