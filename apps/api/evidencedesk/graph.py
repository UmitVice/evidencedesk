"""One-hop document graph expansion applied after rank fusion.

The graph is a retrieval signal only: it decides which tenant chunks enter the bounded context
and annotates them with document relations. Answers still cite verbatim chunk quotes.
"""

from typing import Any

# Relations as seen from the annotated document. Stored `supersedes` and `depends_on` edges are
# directed, so the other endpoint sees `superseded_by` and `required_by`.
INCOMING = {
    "supersedes": "superseded_by",
    "depends_on": "required_by",
    "conflicts_with": "conflicts_with",
    "see_also": "see_also",
}
# Relations whose target is pulled into context when the annotated document is retrieved.
PULLED = ("conflicts_with", "depends_on")


def relations_by_document(edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Index edge rows (joined with both document endpoints) by each endpoint document."""
    result: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}

    def add(document: str, relation: str, prefix: str, edge: dict[str, Any]) -> None:
        target = str(edge[prefix + "_document"])
        result.setdefault(document, {})[(relation, target)] = {
            "relation": relation,
            "document_id": target,
            "source_id": edge[prefix + "_source_id"],
            "title": edge[prefix + "_title"],
            "version": edge[prefix + "_version"],
            "status": edge[prefix + "_status"],
        }

    for edge in edges:
        add(str(edge["from_document"]), edge["relation"], "to", edge)
        add(str(edge["to_document"]), INCOMING[edge["relation"]], "from", edge)
    return {
        document: sorted(
            relations.values(), key=lambda x: (x["relation"], x["source_id"], -x["version"])
        )
        for document, relations in result.items()
    }


def successor(relations: list[dict[str, Any]]) -> str | None:
    """The active document that supersedes an obsolete one, if the corpus has one."""
    current = [x for x in relations if x["relation"] == "superseded_by" and x["status"] == "active"]
    return current[0]["document_id"] if current else None


def neighbors(ranked: list[dict[str, Any]], graph: dict[str, list[dict[str, Any]]]) -> set[str]:
    """Documents that expansion may pull for the ranked rows."""
    wanted: set[str] = set()
    for row in ranked:
        relations = graph.get(str(row["document_id"]), [])
        if row["status"] == "obsolete" and (current := successor(relations)):
            wanted.add(current)
        wanted.update(x["document_id"] for x in relations if x["relation"] in PULLED)
    return wanted


def expand(
    ranked: list[dict[str, Any]],
    graph: dict[str, list[dict[str, Any]]],
    pulled: dict[str, dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Expand ranked rows by one hop and keep at most `limit` rows.

    Pulled rows are placed right after the row that pulled them, so they replace the
    lowest-ranked rows. A superseded row is placed after its current version and is dropped
    when no current version exists, so obsolete text never reaches the context alone.
    `pulled` maps document IDs to their best chunk for the query.
    """
    best: dict[str, dict[str, Any]] = dict(pulled)
    for row in reversed(ranked):
        best[str(row["document_id"])] = row
    out: list[dict[str, Any]] = []
    placed: set[str] = set()
    documents: set[str] = set()

    def place(
        row: dict[str, Any], via: str | None = None, anchor: dict[str, Any] | None = None
    ) -> None:
        if str(row["id"]) in placed:
            return
        placed.add(str(row["id"]))
        documents.add(str(row["document_id"]))
        expansion = {"via": via, "anchor": anchor["source_id"]} if via and anchor else None
        out.append({**row, "expansion": expansion})

    for row in ranked:
        if len(out) >= limit:
            break
        relations = graph.get(str(row["document_id"]), [])
        if row["status"] == "obsolete":
            current = successor(relations)
            if current is None or current not in best:
                continue
            if current not in documents:
                place(best[current], "superseded_by", row)
        place(row)
        for relation in relations:
            target = relation["document_id"]
            if relation["relation"] in PULLED and target not in documents and target in best:
                place(best[target], relation["relation"], row)
    out = out[:limit]
    in_context = {}
    for row in out:
        in_context.setdefault(str(row["document_id"]), str(row["id"]))
    return [
        {
            **row,
            "relations": [
                {**relation, "evidence_id": in_context.get(relation["document_id"])}
                for relation in graph.get(str(row["document_id"]), [])
            ],
        }
        for row in out
    ]
