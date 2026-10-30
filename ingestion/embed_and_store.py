"""Embed chunks with sentence-transformers and upsert into Qdrant.

Loads chunks.jsonl produced by ingestion.chunk, computes embeddings with the
configured model (default: BAAI/bge-base-en-v1.5, 768-dim), and writes them
to the collection the ``municipal_code`` alias points at (one collection per code
vintage, e.g. ``municipal_code_2026-03-18``; see ingestion/push_index.py). With no
alias yet (a fresh checkout), it creates the collection for the vintage in
backend/code_vintage.json and points the alias at it. A code refresh goes through
``ingestion.update``, which embeds into a new collection instead.

Modes:
  --recreate     Drop and rebuild the collection (required after model changes)
  --incremental  Only re-embed sections whose content changed since last run
  --collection   Write to this collection instead of the alias target
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
from backend.config import get_settings

from .code_vintage import CODE_ALIAS, collection_for, load_code_vintage
from .manifest import (
    build_manifest,
    diff_manifests,
    load_manifest,
    save_manifest,
    set_chunk_counts,
)
from .push_index import alias_target, switch_alias


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


def delete_sections(client: QdrantClient, collection: str, section_ids) -> None:
    for section_id in section_ids:
        _delete_section_points(client, collection, section_id)


def _embed_and_buffer(
    model, batch: list[dict], buffer: list[PointStruct]
) -> None:
    texts = [c["text"] for c in batch]
    vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    for chunk, vec in zip(batch, vectors):
        buffer.append(PointStruct(id=str(uuid.uuid4()), vector=vec.tolist(), payload=chunk))


def _run_incremental(client: QdrantClient, model, collection: str) -> None:
    old_manifest = load_manifest()
    if not old_manifest:
        log.warning("No existing manifest -- falling back to full rebuild")
        embed_chunks(client, model, collection)
        _save_manifest_from_sections()
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
    delete_sections(client, collection, diff.deleted + diff.modified)
    if diff.deleted:
        log.info("Deleted points for %d removed section(s)", len(diff.deleted))

    total = embed_chunks(client, model, collection, only_sections=affected_sections) if affected_sections else 0
    set_chunk_counts(new_manifest, CHUNKS_FILE)
    save_manifest(new_manifest)
    log.info("Incremental update done -- %d chunks re-embedded", total)


def embed_chunks(
    client: QdrantClient,
    model,
    collection: str,
    chunks_path: Path = CHUNKS_FILE,
    *,
    only_sections: set[str] | None = None,
) -> int:
    """Embed chunks (all, or only those of ``only_sections``) into ``collection``."""
    buffer: list[PointStruct] = []
    total = 0

    def flush() -> None:
        nonlocal buffer
        if buffer:
            client.upsert(collection, points=buffer, wait=True)
            buffer = []

    opener = gzip.open if chunks_path.suffix == ".gz" else open
    with opener(chunks_path, "rt") as fh:
        batch: list[dict] = []
        for line in fh:
            chunk = json.loads(line)
            if only_sections is not None and chunk.get("section") not in only_sections:
                continue
            batch.append(chunk)
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
    log.info("Done. %d chunks embedded into %s.", total, collection)
    return total


def _save_manifest_from_sections() -> None:
    if SECTIONS_DIR.exists():
        manifest = build_manifest(SECTIONS_DIR)
        set_chunk_counts(manifest, CHUNKS_FILE)
        save_manifest(manifest)
        log.info("Saved manifest with %d sections", len(manifest))


def resolve_collection(client: QdrantClient) -> str:
    """The collection behind the alias; without one, the collection for the vintage in
    backend/code_vintage.json."""
    target = alias_target(client, CODE_ALIAS)
    if target:
        return target
    vintage = load_code_vintage() or {}
    if not vintage.get("current_through"):
        raise SystemExit("No municipal_code alias and no backend/code_vintage.json; pass --collection")
    return collection_for(vintage["current_through"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recreate", action="store_true", help="Drop and recreate the collection")
    parser.add_argument("--incremental", action="store_true", help="Only re-embed changed sections")
    parser.add_argument("--collection", default=None, help="Target collection (default: the alias target)")
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

    from sentence_transformers import SentenceTransformer

    log.info("Loading embedding model %s", settings.embedding_model)
    model = SentenceTransformer(settings.embedding_model)

    client = QdrantClient(url=settings.qdrant_url)
    collection = args.collection or resolve_collection(client)
    if args.recreate:
        try:
            client.delete_collection(collection)
            log.info("Deleted collection %s", collection)
        except Exception:
            pass
    _ensure_collection(client, collection, settings.embedding_dim)
    # Deleting a collection drops its aliases too, so this also covers --recreate.
    if not args.collection and alias_target(client, CODE_ALIAS) != collection:
        switch_alias(client, collection, CODE_ALIAS)
        log.info("Pointed alias %s at %s", CODE_ALIAS, collection)
    if args.chunks and not args.recreate:
        # Point ids are random, so embedding a sample into a populated collection
        # would duplicate every chunk it shares with the corpus.
        existing = client.count(collection).count
        if existing:
            raise SystemExit(
                f"{collection} already has {existing} points; "
                "--chunks is for seeding an empty Qdrant (add --recreate to replace it)."
            )

    if args.incremental:
        _run_incremental(client, model, collection)
    else:
        embed_chunks(client, model, collection, chunks_path)
        if args.chunks is None:
            _save_manifest_from_sections()


if __name__ == "__main__":
    main()
