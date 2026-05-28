"""Embed chunks with sentence-transformers and upsert into Qdrant.

Loads chunks.jsonl produced by ingestion.chunk, computes embeddings with
BAAI/bge-small-en-v1.5 (384-dim, 512-token context), and writes them to two
Qdrant collections:
- chicago_municipal_code (all chunks)
- chicago_zoning (only Title 17 chunks — enables filter-free zoning queries)
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from backend.config import get_settings


log = logging.getLogger(__name__)

CHUNKS_FILE = Path(__file__).resolve().parent / "data" / "chunks.jsonl"
BATCH_SIZE = 128


def _ensure_collection(client: QdrantClient, name: str, size: int) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        return
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=size, distance=Distance.COSINE),
    )
    log.info("Created Qdrant collection %s (size=%d)", name, size)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()

    if not CHUNKS_FILE.exists():
        raise SystemExit(f"No chunks at {CHUNKS_FILE} — run ingestion.chunk first")

    log.info("Loading embedding model %s", settings.embedding_model)
    model = SentenceTransformer(settings.embedding_model)

    client = QdrantClient(url=settings.qdrant_url)
    _ensure_collection(client, settings.qdrant_code_collection, settings.embedding_dim)
    _ensure_collection(client, settings.qdrant_zoning_collection, settings.embedding_dim)

    code_buffer: list[PointStruct] = []
    zoning_buffer: list[PointStruct] = []
    total = 0

    def flush() -> None:
        nonlocal code_buffer, zoning_buffer
        if code_buffer:
            client.upsert(settings.qdrant_code_collection, points=code_buffer)
            code_buffer = []
        if zoning_buffer:
            client.upsert(settings.qdrant_zoning_collection, points=zoning_buffer)
            zoning_buffer = []

    with CHUNKS_FILE.open() as fh:
        batch: list[dict] = []
        for line in fh:
            batch.append(json.loads(line))
            if len(batch) >= BATCH_SIZE:
                _embed_and_buffer(model, batch, code_buffer, zoning_buffer)
                total += len(batch)
                batch = []
                if total % (BATCH_SIZE * 4) == 0:
                    log.info("Embedded %d chunks", total)
                    flush()
        if batch:
            _embed_and_buffer(model, batch, code_buffer, zoning_buffer)
            total += len(batch)

    flush()
    log.info("Done. %d chunks total.", total)


def _embed_and_buffer(model, batch: list[dict], code_buffer: list[PointStruct], zoning_buffer: list[PointStruct]) -> None:
    texts = [c["text"] for c in batch]
    vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    for chunk, vec in zip(batch, vectors):
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vec.tolist(),
            payload=chunk,
        )
        code_buffer.append(point)
        if chunk.get("title_number") == 17:
            zoning_buffer.append(point)


if __name__ == "__main__":
    main()
