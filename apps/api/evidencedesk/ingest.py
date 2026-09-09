import hashlib
import json
import re
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from evidencedesk.db import connection

DATA = Path(__file__).resolve().parents[1] / "data" / "knowledge"
FIXTURE_MANIFEST = {
    "model": "fixture-hash-v1",
    "dimension": 384,
    "pooling": "none",
    "preprocessing": "english-word-hash-v1",
    "corpus_version": "1",
}


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tenant: Literal["harbor", "summit"]
    source_id: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=1, max_length=160)
    version: int = Field(ge=1)
    status: Literal["active", "obsolete"]
    product: Literal["RelayNest"]


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
    result = []
    for section in re.split(r"(?m)^## ", body):
        heading, _, text = section.strip().partition("\n")
        if text.strip():
            result.append((heading.removeprefix("# "), text.strip()))
    return result


def seed() -> int:
    count = 0
    with connection(migration=True) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(1002)")
        for path in sorted(DATA.glob("*.md")):
            meta, body = read_document(path)
            doc_id = uuid5(
                NAMESPACE_URL, f"relaynest:{meta.tenant}:{meta.source_id}:{meta.version}"
            )
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
                if existing and existing["embedding_manifest"] != FIXTURE_MANIFEST:
                    raise ValueError("Live corpus changed: use explicit live ingestion")
                conn.execute(
                    "INSERT INTO evidence.chunks(id,document_id,tenant,heading,body,"
                    "content_hash,embedding,embedding_manifest) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s::vector,%s::jsonb) "
                    "ON CONFLICT(id) DO UPDATE SET heading=EXCLUDED.heading,"
                    "body=EXCLUDED.body,content_hash=EXCLUDED.content_hash,"
                    "embedding=EXCLUDED.embedding",
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
    return count
