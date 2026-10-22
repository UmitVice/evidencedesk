"""Score a model on the held-out products (FlagForge in English, Fatura Bulutu in Turkish).

The prompts are the exact validation prompts; the model is called through an OpenAI-compatible
endpoint (llama.cpp with or without the LoRA adapter) and scored with the production validators.
Teacher answers are only used for the expected status, never as a string-match reference.
"""

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

import httpx
from evidencedesk.errors import DomainError
from evidencedesk.providers import answer_json_schema
from evidencedesk.workflow import validate_response


def evidence_from(messages: list[dict]) -> list[dict]:
    payload = json.loads(messages[1]["content"])
    return [{"id": row["source_id"], "body": row["passage"]} for row in payload["evidence"]]


def score(base_url: str, model: str, data: Path, limit: int, constrained: bool) -> dict:
    rows = [json.loads(x) for x in (data / "valid.jsonl").read_text().splitlines() if x]
    metas = [json.loads(x) for x in (data / "valid.meta.jsonl").read_text().splitlines() if x]
    results = []
    for row, meta in list(zip(rows, metas, strict=True))[:limit]:
        messages = row["messages"][:-1]
        evidence = evidence_from(messages)
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 700,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if constrained:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "answer",
                    "strict": True,
                    "schema": answer_json_schema([e["id"] for e in evidence]),
                },
            }
        started = time.perf_counter()
        response = httpx.post(base_url.rstrip("/") + "/chat/completions", json=payload, timeout=300)
        elapsed = time.perf_counter() - started
        data_json = response.json()
        content = data_json["choices"][0]["message"].get("content") or ""
        outcome = {
            "kind": meta["kind"],
            "language": meta["language"],
            "elapsed_s": elapsed,
            "completion_tokens": (data_json.get("usage") or {}).get("completion_tokens"),
        }
        try:
            answer = validate_response(content, evidence)
            outcome |= {"valid": True, "status_ok": answer.status == meta["expected"]}
        except DomainError as exc:
            outcome |= {"valid": False, "status_ok": False, "error": exc.code}
        results.append(outcome)

    def rates(items: list[dict]) -> dict:
        n = len(items)
        return {
            "n": n,
            "valid_rate": round(sum(x["valid"] for x in items) / n, 4) if n else None,
            "pass_rate": round(sum(x["status_ok"] for x in items) / n, 4) if n else None,
        }

    by_language: dict[str, list[dict]] = defaultdict(list)
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for item in results:
        by_language[item["language"]].append(item)
        by_kind[item["kind"]].append(item)
    tokens = [x["completion_tokens"] for x in results if x["completion_tokens"]]
    return {
        "model": model,
        "constrained_decoding": constrained,
        "overall": rates(results),
        "by_language": {k: rates(v) for k, v in sorted(by_language.items())},
        "by_kind": {k: rates(v) for k, v in sorted(by_kind.items())},
        "errors": dict(Counter(x.get("error") for x in results if x.get("error"))),
        "latency_p50_s": round(statistics.median(x["elapsed_s"] for x in results), 2),
        "completion_tokens_mean": round(statistics.mean(tokens), 1) if tokens else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", required=True)
    default_data = Path(__file__).resolve().parents[1] / "data" / "sft"
    parser.add_argument("--data", type=Path, default=default_data)
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--no-constrained", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = score(args.base_url, args.model, args.data, args.limit, not args.no_constrained)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report["overall"]), json.dumps(report["by_language"]))


if __name__ == "__main__":
    main()
