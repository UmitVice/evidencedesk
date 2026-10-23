import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Literal, NamedTuple
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field

from evidencedesk.db import connection
from evidencedesk.tokenization import token_count

DATA = Path(__file__).resolve().parents[1] / "data" / "knowledge"
FIXTURE_MANIFEST = {
    "model": "fixture-hash-v1",
    "dimension": 384,
    "pooling": "none",
    "preprocessing": "english-word-hash-v1",
    "corpus_version": "1",
}


Relation = Literal["supersedes", "conflicts_with", "depends_on", "see_also"]
SYMMETRIC: frozenset[str] = frozenset({"conflicts_with", "see_also"})


class Related(BaseModel):
    """An explicit document relation declared in front matter, resolved within the tenant."""

    model_config = ConfigDict(extra="forbid", strict=True)
    source_id: str = Field(pattern=r"^[a-z0-9-]+$")
    relation: Relation


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tenant: Literal["harbor", "summit"]
    source_id: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=1, max_length=160)
    version: int = Field(ge=1)
    status: Literal["active", "obsolete"]
    product: Literal["RelayNest"]
    related: list[Related] = Field(default_factory=list, max_length=8)


Origin = Literal["version", "front_matter"]


class Edge(NamedTuple):
    tenant: str
    from_document: UUID
    to_document: UUID
    relation: Relation
    origin: Origin


def document_id(meta: Metadata) -> UUID:
    return uuid5(NAMESPACE_URL, f"relaynest:{meta.tenant}:{meta.source_id}:{meta.version}")


def derive_edges(documents: Iterable[Metadata]) -> list[Edge]:
    """Derive the tenant-scoped document graph from metadata alone.

    A higher version of a source supersedes every lower version, so one hop always reaches the
    current text. Front-matter targets resolve to the active version of a source in the same
    tenant; symmetric relations are stored in both directions.
    """
    versions: dict[tuple[str, str], list[Metadata]] = {}
    for meta in documents:
        versions.setdefault((meta.tenant, meta.source_id), []).append(meta)
    edges: dict[tuple[str, UUID, UUID, str], Edge] = {}

    def add(tenant: str, start: UUID, end: UUID, relation: Relation, origin: Origin) -> None:
        if start == end:
            raise ValueError("A document cannot relate to itself")
        edges.setdefault((tenant, start, end, relation), Edge(tenant, start, end, relation, origin))

    for (tenant, source_id), group in versions.items():
        group.sort(key=lambda meta: meta.version)
        if len({meta.version for meta in group}) != len(group):
            raise ValueError(f"Duplicate version for {source_id}")
        active = [meta for meta in group if meta.status == "active"]
        if len(active) > 1:
            raise ValueError(f"More than one active version for {source_id}")
        if active and active[0] is not group[-1]:
            raise ValueError(f"An obsolete version of {source_id} is newer than the active one")
        for index, newer in enumerate(group):
            for older in group[:index]:
                add(tenant, document_id(newer), document_id(older), "supersedes", "version")
    for group in versions.values():
        for meta in group:
            for related in meta.related:
                targets = versions.get((meta.tenant, related.source_id))
                if not targets:
                    raise ValueError(
                        f"{meta.source_id} relates to unknown source {related.source_id} "
                        f"in tenant {meta.tenant}"
                    )
                target = next((x for x in targets if x.status == "active"), targets[-1])
                start, end = document_id(meta), document_id(target)
                add(meta.tenant, start, end, related.relation, "front_matter")
                if related.relation in SYMMETRIC:
                    add(meta.tenant, end, start, related.relation, "front_matter")
    return sorted(edges.values(), key=lambda edge: (edge.tenant, str(edge.from_document)))


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def fixture_vector(text: str) -> list[float]:
    vector = [0.0] * 384
    for word in re.findall(r"[a-z]+", text.lower()):
        vector[int(digest(word)[:8], 16) % 384] += 1
    return vector


def read_document(path: Path) -> tuple[Metadata, str]:
    _, header, body = path.read_text().split("---", 2)
    return Metadata.model_validate_json(header), body.strip()


def chunks(body: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for section in re.split(r"(?m)^## ", body):
        heading, _, text = section.strip().partition("\n")
        heading = heading.removeprefix("# ")
        current = ""
        for paragraph in text.strip().split("\n\n"):
            for word in paragraph.split():
                candidate = (current + " " + word).strip()
                if token_count(heading + "\n" + candidate) > 350:
                    if not current:
                        raise ValueError("A word exceeds the embedding budget")
                    result.append((heading, current))
                    current = word
                else:
                    current = candidate
            if current and token_count(heading + "\n" + current) >= 250:
                result.append((heading, current))
                current = ""
        if current:
            if token_count(heading + "\n" + current) > 512:
                raise ValueError("Embedding input exceeds model token limit")
            result.append((heading, current))
    return result


def seed(*, for_live: bool = False) -> int:
    count = 0
    documents = [read_document(path) for path in sorted(DATA.glob("*.md"))]
    edges = derive_edges(meta for meta, _ in documents)
    with connection(migration=True) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(1002)")
        for meta, body in documents:
            doc_id = document_id(meta)
            conn.execute(
                "INSERT INTO evidence.documents VALUES(%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(id) DO UPDATE SET title=EXCLUDED.title, "
                "status=EXCLUDED.status,content_hash=EXCLUDED.content_hash",
                (
                    doc_id,
                    meta.tenant,
                    meta.source_id,
                    meta.title,
                    meta.version,
                    meta.status,
                    digest(body),
                ),
            )
            keep = []
            for index, (heading, text) in enumerate(chunks(body)):
                chunk_id = uuid5(doc_id, str(index))
                keep.append(chunk_id)
                existing = conn.execute(
                    "SELECT content_hash,embedding_manifest FROM evidence.chunks WHERE id=%s",
                    (chunk_id,),
                ).fetchone()
                content_hash = digest(heading + "\n" + text)
                if existing and existing["content_hash"] == content_hash:
                    continue
                if existing and existing["embedding_manifest"] != FIXTURE_MANIFEST and not for_live:
                    raise ValueError("Live corpus changed: use explicit live ingestion")
                conn.execute(
                    "INSERT INTO evidence.chunks(id,document_id,tenant,heading,body,"
                    "content_hash,embedding,embedding_manifest) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s::vector,%s::jsonb) "
                    "ON CONFLICT(id) DO UPDATE SET heading=EXCLUDED.heading,"
                    "body=EXCLUDED.body,content_hash=EXCLUDED.content_hash,"
                    "embedding=EXCLUDED.embedding,embedding_manifest=EXCLUDED.embedding_manifest",
                    (
                        chunk_id,
                        doc_id,
                        meta.tenant,
                        heading,
                        text,
                        content_hash,
                        str(fixture_vector(heading + " " + text)),
                        json.dumps(FIXTURE_MANIFEST),
                    ),
                )
                count += 1
            conn.execute(
                "DELETE FROM evidence.chunks WHERE document_id=%s AND NOT(id=ANY(%s))",
                (doc_id, keep),
            )
        # The graph is fully derived from the corpus, so it is rebuilt in the same transaction.
        conn.execute("DELETE FROM evidence.document_edges")
        with conn.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO evidence.document_edges"
                "(tenant,from_document,to_document,relation,origin) VALUES(%s,%s,%s,%s,%s)",
                edges,
            )
    return count
