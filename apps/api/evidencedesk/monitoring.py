"""Cross-session views of live analyses for the maintainer.

`quality_summary` returns counts only and backs the public evaluation page; it never returns
ticket text, questions, or answers. `review_report` renders flagged analyses with their content
into a local HTML file for the maintainer and is only reachable from the command line.
"""

import html
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evidencedesk.db import connection
from evidencedesk.quality import FLAGS

FLAGGED = (
    "EXISTS (SELECT 1 FROM jsonb_array_elements(COALESCE(r.trace->'review_flags','[]'::jsonb)) f "
    "WHERE f->>'severity'='review')"
)


def quality_summary(days: int = 7, *, review: bool = False) -> dict[str, Any]:
    with connection(review=review) as conn:
        totals = conn.execute(
            "SELECT count(*) FILTER (WHERE r.status='complete') complete,"
            "count(*) FILTER (WHERE r.status='failed') failed,"
            f"count(*) FILTER (WHERE r.status='complete' AND {FLAGGED}) flagged "
            "FROM evidence.runs r WHERE r.mode='live' "
            "AND r.created_at > now() - make_interval(days => %s)",
            (days,),
        ).fetchone()
        codes = conn.execute(
            "SELECT f->>'code' code,count(*) n FROM evidence.runs r,"
            "jsonb_array_elements(COALESCE(r.trace->'review_flags','[]'::jsonb)) f "
            "WHERE r.mode='live' AND r.status='complete' "
            "AND r.created_at > now() - make_interval(days => %s) "
            "GROUP BY 1 ORDER BY 2 DESC,1",
            (days,),
        ).fetchall()
        models = conn.execute(
            "SELECT r.trace->>'generation_model' model,count(*) n FROM evidence.runs r "
            "WHERE r.mode='live' AND r.status='complete' "
            "AND COALESCE((r.trace->>'attempts')::int,0)>0 "
            "AND r.created_at > now() - make_interval(days => %s) "
            "GROUP BY 1 ORDER BY 2 DESC,1",
            (days,),
        ).fetchall()
    assert totals
    return {
        "days": days,
        "complete": totals["complete"],
        "failed": totals["failed"],
        "flagged": totals["flagged"],
        "flags": [
            {"code": row["code"], "count": row["n"]} for row in codes if row["code"] in FLAGS
        ],
        "models": [{"model": row["model"] or "unknown", "count": row["n"]} for row in models],
        "generated_at": datetime.now(UTC),
    }


def flagged_runs(days: int, limit: int = 200) -> list[dict[str, Any]]:
    with connection(review=True) as conn:
        return conn.execute(
            "SELECT r.id,r.created_at,r.question,t.title,t.body ticket,r.result,"
            "r.trace->'review_flags' flags,r.trace->>'generation_model' model "
            "FROM evidence.runs r JOIN evidence.tickets t "
            "ON t.id=r.ticket_id AND t.session_id=r.session_id AND t.tenant=r.tenant "
            f"WHERE r.mode='live' AND r.status='complete' AND {FLAGGED} "
            "AND r.created_at > now() - make_interval(days => %s) "
            "ORDER BY r.created_at DESC LIMIT %s",
            (days, limit),
        ).fetchall()


def render_report(summary: dict[str, Any], runs: list[dict[str, Any]]) -> str:
    def e(value: Any) -> str:
        return html.escape(str(value if value is not None else ""))

    items = []
    for run in runs:
        result = run["result"] or {}
        flags = "".join(
            f"<li><strong>{e(f['code'])}</strong>: {e(f['message'])}</li>"
            for f in run["flags"] or []
            if f.get("severity") == "review"
        )
        claims = "".join(
            "<li>"
            + e(claim.get("text"))
            + "".join(
                f"<blockquote>{e(c.get('quote'))}</blockquote>"
                for c in claim.get("citations", [])
            )
            + "</li>"
            for claim in result.get("claims", [])
        )
        items.append(
            f"<article><h2>{e(run['title'])}</h2>"
            f"<p class=meta>{e(run['created_at'])} · {e(run['model'])} · run {e(run['id'])}</p>"
            f"<p><strong>Question:</strong> {e(run['question'] or run['ticket'])}</p>"
            f"<ul class=flags>{flags}</ul><ol>{claims}</ol>"
            f"<p><strong>Draft note:</strong> {e(result.get('proposed_note'))}</p></article>"
        )
    counts = ", ".join(f"{e(f['code'])} {f['count']}" for f in summary["flags"]) or "none"
    return (
        "<!doctype html><meta charset=utf-8><title>EvidenceDesk flagged analyses</title>"
        "<style>body{font:15px/1.5 system-ui;max-width:900px;margin:2rem auto;padding:0 1rem}"
        "article{border:1px solid #ccc;border-radius:8px;padding:1rem;margin:1rem 0}"
        ".meta{color:#666;font-size:13px}.flags{color:#9a3412}"
        "blockquote{margin:.3rem 0 .3rem 1rem;color:#444;border-left:3px solid #ddd;"
        "padding-left:.6rem}</style>"
        f"<h1>Flagged analyses, last {summary['days']} days</h1>"
        f"<p>{summary['complete']} completed live analyses, {summary['flagged']} flagged, "
        f"{summary['failed']} failed. Flags: {counts}.</p>"
        + ("".join(items) or "<p>No flagged analyses.</p>")
    )


def review_report(output: Path, days: int = 7) -> int:
    runs = flagged_runs(days)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(quality_summary(days, review=True), runs))
    output.chmod(0o600)
    return len(runs)
