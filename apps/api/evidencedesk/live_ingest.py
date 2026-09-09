import json
from pathlib import Path

from evidencedesk.config import settings
from evidencedesk.db import connection
from evidencedesk.errors import DomainError
from evidencedesk.ingest import DATA, digest, read_document, seed
from evidencedesk.providers import LIVE_MANIFEST, CloudflareProvider
from evidencedesk.quotas import reserve
from evidencedesk.tokenization import check_embedding_input


def ingest_live(max_batches: int = 2) -> int:
    if settings().environment == "production":
        raise DomainError(
            "development_only", "Live ingestion must be validated in development first."
        )
    seed()
    with connection(migration=True) as conn:
        pending = conn.execute(
            "SELECT id,heading,body,content_hash FROM evidence.chunks "
            "WHERE embedding_manifest<>%s::jsonb ORDER BY id",
            (json.dumps(LIVE_MANIFEST),),
        ).fetchall()
    if len(pending) > max_batches * 16:
        raise ValueError("Pending corpus exceeds explicit embedding batch cap")
    changed = []
    for start in range(0, len(pending), 16):
        batch = pending[start : start + 16]
        texts = [row["heading"] + "\n" + row["body"] for row in batch]
        for text in texts:
            check_embedding_input(text)
        reserve({"id": "maintenance-ingestion"}, retry=True)
        vectors = CloudflareProvider().embed(texts)
        changed.extend(zip(batch, vectors, strict=True))
    with connection(migration=True) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(1002)")
        for row, vector in changed:
            updated = conn.execute(
                "UPDATE evidence.chunks SET embedding=%s::vector,"
                "embedding_manifest=%s::jsonb WHERE id=%s AND content_hash=%s "
                "RETURNING id",
                (str(vector), json.dumps(LIVE_MANIFEST), row["id"], row["content_hash"]),
            ).fetchone()
            if not updated:
                raise ValueError("Corpus changed during embedding; transaction rolled back")
    return len(changed)


def corpus_hash() -> str:
    return digest("".join(path.read_text() for path in sorted(DATA.glob("*.md"))))


def verify_corpus(path: Path = DATA) -> int:
    count = 0
    for file in sorted(path.glob("*.md")):
        meta, _ = read_document(file)
        if not meta.title:
            raise ValueError("Missing document title")
        count += 1
    return count
