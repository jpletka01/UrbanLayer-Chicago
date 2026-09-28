"""Embed chunks with sentence-transformers and upsert into Qdrant.

Loads chunks.jsonl produced by ingestion.chunk, computes embeddings with the
configured model (default: BAAI/bge-base-en-v1.5, 768-dim), and writes them
to the chicago_municipal_code Qdrant collection. (A second, Title-17-only
collection used to be written too; nothing ever searched it, and it was removed.)

Modes:
  --recreate     Drop and rebuild collections (required after model changes)
  --incremental  Only re-embed sections whose content changed since last run
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import uuid
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

from backend.config import get_settings

from .manifest import (
    build_manifest,
    diff_manifests,
    load_manifest,
    save_manifest,
    set_chunk_counts,
)


log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
CHUNKS_FILE = DATA_DIR / "chunks.jsonl"
SECTIONS_DIR = DATA_DIR / "sections"
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


def _delete_section_points(
    client: QdrantClient, collection: str, section_id: str
) -> None:
    client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[FieldCondition(key="section", match=MatchValue(value=section_id))]
        ),
    )


def _embed_and_buffer(
    model, batch: list[dict], buffer: list[PointStruct]
) -> None:
    texts = [c["text"] for c in batch]
    vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    for chunk, vec in zip(batch, vectors):
        buffer.append(PointStruct(id=str(uuid.uuid4()), vector=vec.tolist(), payload=chunk))


def _run_incremental(client: QdrantClient, model: SentenceTransformer) -> None:
    settings = get_settings()
    old_manifest = load_manifest()
    if not old_manifest:
        log.warning("No existing manifest -- falling back to full rebuild")
        _run_full(client, model, save_new_manifest=True)
        return

    new_manifest = build_manifest(SECTIONS_DIR)
    diff = diff_manifests(old_manifest, new_manifest)

    if diff.total_changes == 0:
        log.info("No changes detected -- nothing to do")
        return

    log.info(
        "Changes: %d added, %d modified, %d deleted",
        len(diff.added),
        len(diff.modified),
        len(diff.deleted),
    )

    affected_sections = set(diff.added) | set(diff.modified)
    collection = settings.qdrant_code_collection

    for section_id in diff.deleted:
        _delete_section_points(client, collection, section_id)
        log.info("Deleted points for section %s", section_id)

    for section_id in diff.modified:
        _delete_section_points(client, collection, section_id)

    if not affected_sections:
        set_chunk_counts(new_manifest, CHUNKS_FILE)
        save_manifest(new_manifest)
        log.info("Done -- only deletions")
        return

    buffer: list[PointStruct] = []
    total = 0

    def flush() -> None:
        nonlocal buffer
        if buffer:
            client.upsert(settings.qdrant_code_collection, points=buffer)
            buffer = []

    with CHUNKS_FILE.open() as fh:
        batch: list[dict] = []
        for line in fh:
            chunk = json.loads(line)
            if chunk.get("section") not in affected_sections:
                continue
            batch.append(chunk)
            if len(batch) >= BATCH_SIZE:
                _embed_and_buffer(model, batch, buffer)
                total += len(batch)
                batch = []
                flush()
        if batch:
            _embed_and_buffer(model, batch, buffer)
            total += len(batch)

    flush()
    set_chunk_counts(new_manifest, CHUNKS_FILE)
    save_manifest(new_manifest)
    log.info("Incremental update done -- %d chunks re-embedded", total)


def _run_full(
    client: QdrantClient,
    model: SentenceTransformer,
    *,
    save_new_manifest: bool = False,
    chunks_path: Path = CHUNKS_FILE,
) -> None:
    settings = get_settings()
    buffer: list[PointStruct] = []
    total = 0

    def flush() -> None:
        nonlocal buffer
        if buffer:
            client.upsert(settings.qdrant_code_collection, points=buffer)
            buffer = []

    opener = gzip.open if chunks_path.suffix == ".gz" else open
    with opener(chunks_path, "rt") as fh:
        batch: list[dict] = []
        for line in fh:
            batch.append(json.loads(line))
            if len(batch) >= BATCH_SIZE:
                _embed_and_buffer(model, batch, buffer)
                total += len(batch)
                batch = []
                if total % (BATCH_SIZE * 4) == 0:
                    log.info("Embedded %d chunks", total)
                    flush()
        if batch:
            _embed_and_buffer(model, batch, buffer)
            total += len(batch)

    flush()
    log.info("Done. %d chunks total.", total)

    if save_new_manifest and SECTIONS_DIR.exists():
        manifest = build_manifest(SECTIONS_DIR)
        set_chunk_counts(manifest, CHUNKS_FILE)
        save_manifest(manifest)
        log.info("Saved manifest with %d sections", len(manifest))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recreate", action="store_true", help="Drop and recreate collections")
    parser.add_argument("--incremental", action="store_true", help="Only re-embed changed sections")
    parser.add_argument(
        "--chunks", type=Path, default=None,
        help="Embed this chunks file (.jsonl or .jsonl.gz) instead of the full corpus, e.g. "
             "ingestion/sample/chunks_t16_17.jsonl.gz for a local demo. Skips the manifest.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()

    chunks_path = args.chunks or CHUNKS_FILE
    if not chunks_path.exists():
        raise SystemExit(f"No chunks at {chunks_path} -- run ingestion.chunk first")

    log.info("Loading embedding model %s", settings.embedding_model)
    model = SentenceTransformer(settings.embedding_model)

    client = QdrantClient(url=settings.qdrant_url)
    if args.recreate:
        try:
            client.delete_collection(settings.qdrant_code_collection)
            log.info("Deleted collection %s", settings.qdrant_code_collection)
        except Exception:
            pass
    _ensure_collection(client, settings.qdrant_code_collection, settings.embedding_dim)
    if args.chunks and not args.recreate:
        # Point ids are random, so embedding a sample into a populated collection
        # would duplicate every chunk it shares with the corpus.
        existing = client.count(settings.qdrant_code_collection).count
        if existing:
            raise SystemExit(
                f"{settings.qdrant_code_collection} already has {existing} points; "
                "--chunks is for seeding an empty Qdrant (add --recreate to replace it)."
            )

    if args.incremental:
        _run_incremental(client, model)
    else:
        _run_full(client, model, save_new_manifest=args.chunks is None, chunks_path=chunks_path)


if __name__ == "__main__":
    main()
