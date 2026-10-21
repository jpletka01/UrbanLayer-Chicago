"""Unified update CLI for the ingestion pipeline.

Usage:
    python -m ingestion.update --dry-run [--source export.html]   # parse + diff only
    python -m ingestion.update [--source export.html]             # apply (embed, then promote)
    python -m ingestion.update --full                             # re-embed every chunk
    python -m ingestion.update --manifest                         # just rebuild the manifest

Every run parses the export into ``ingestion/data/sections.new/`` and chunks it into
``chunks.new.jsonl``, then writes ``ingestion/data/diff/<vintage>/{diff.json,report.md}``
(see ingestion/diff_report.py) and checks the abort gates.

``--dry-run`` stops there. It never touches ``sections/``, ``chunks.jsonl``, the
manifest, ``backend/code_vintage.json`` or Qdrant.

Applying embeds first and promotes after:

1. A new vintage is embedded in full into its own collection,
   ``municipal_code_<vintage>``. The collection serving now is left alone.
   The same vintage (a parser fix) is updated in place: removed and modified
   sections are deleted, and added and modified ones embedded.
2. The point count must equal the chunk count. Otherwise nothing is promoted.
3. Only then are the previous corpus files moved to ``ingestion/data/snapshots/<old
   vintage>/`` (for rollback), the staged files promoted, the local ``municipal_code``
   alias pointed at the new collection, and ``backend/code_vintage.json`` and
   ``backend/code_changes.json`` written.

Prod gets the collection afterwards through ``ingestion.push_index``.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .code_vintage import (
    CODE_ALIAS,
    VINTAGE_FILE,
    collection_for,
    load_code_vintage,
    read_export_vintage,
    write_code_vintage,
)
from .diff_report import build_diff, gate_failures, write_report
from .manifest import (
    MANIFEST_FILE,
    build_manifest,
    diff_manifests,
    load_manifest,
    save_manifest,
    set_chunk_counts,
)
from .source_check import SOURCE_HASH_FILE, save_hash


log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
SECTIONS_DIR = DATA_DIR / "sections"
SECTIONS_NEW = DATA_DIR / "sections.new"
CHUNKS_FILE = DATA_DIR / "chunks.jsonl"
CHUNKS_NEW = DATA_DIR / "chunks.new.jsonl"
DIFF_DIR = DATA_DIR / "diff"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
CHANGES_FILE = DATA_DIR.parent.parent / "backend" / "code_changes.json"
# Same location parse_chicago_code.py reads (and the README documents): the repo root.
SOURCE_HTML = DATA_DIR.parent.parent / "chicago-il-codes.html"


def stage(source: Path) -> tuple[dict, list[str], dict, str]:
    """Parse + chunk into the staging paths and write the diff report.

    Returns (diff, gate failures, new manifest, new vintage date).
    """
    from .chunk import write_chunks
    from .parse_chicago_code import write_sections

    new_vintage = read_export_vintage(source)["current_through"]
    old_vintage = (load_code_vintage(VINTAGE_FILE) or {}).get("current_through")

    write_sections(source, SECTIONS_NEW)
    write_chunks(SECTIONS_NEW, CHUNKS_NEW)
    new_manifest = build_manifest(SECTIONS_NEW)
    set_chunk_counts(new_manifest, CHUNKS_NEW)
    old_manifest = load_manifest(MANIFEST_FILE)

    diff = build_diff(
        SECTIONS_DIR, SECTIONS_NEW, old_manifest, new_manifest,
        old_vintage=old_vintage, new_vintage=new_vintage,
    )
    failures = gate_failures(diff)
    report = write_report(diff, failures, DIFF_DIR / new_vintage)
    log.info(
        "Diff %s -> %s: %d added, %d modified, %d deleted (of %d sections). Report: %s",
        old_vintage, new_vintage, len(diff["added"]), len(diff["modified"]),
        len(diff["deleted"]), len(new_manifest), report,
    )
    for f in failures:
        log.error("Abort gate: %s", f)

    # Flag the precomputed zoning cache if any Title-17 section changed (it's
    # built off the zoning ordinance). Best-effort: never let it break ingestion.
    try:
        from backend.zoning_cache_build import staleness_flag

        flag = staleness_flag(diff_manifests(old_manifest, new_manifest), new_manifest, old_manifest)
        if flag:
            log.warning(flag)
    except Exception as exc:  # pragma: no cover - advisory only
        log.debug("Zoning-cache staleness check skipped: %s", exc)

    return diff, failures, new_manifest, new_vintage


def embed(client, model, diff: dict, collection: str, live: str | None, *, full: bool) -> None:
    """Get ``collection`` to hold exactly the staged chunks."""
    from qdrant_client.models import Distance, VectorParams

    from .embed_and_store import delete_sections, embed_chunks

    exists = client.collection_exists(collection)
    if collection == live and not full:
        delete_sections(client, collection, diff["deleted"] + diff["modified"])
        changed = set(diff["added"]) | set(diff["modified"])
        if changed:
            embed_chunks(client, model, collection, CHUNKS_NEW, only_sections=changed)
        return
    if collection == live:
        raise SystemExit(
            f"--full would rebuild {collection}, which the {CODE_ALIAS} alias serves now. "
            "Run without --full (in-place update), or point the alias elsewhere first."
        )
    if exists:
        if client.count(collection, exact=True).count and not full:
            raise SystemExit(f"{collection} already has points; pass --full to rebuild it")
        client.delete_collection(collection)
    dim = model.get_sentence_embedding_dimension()
    client.create_collection(collection, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
    embed_chunks(client, model, collection, CHUNKS_NEW)


def _chunk_total(path: Path) -> int:
    with path.open() as fh:
        return sum(1 for _ in fh)


def _snapshot_current(old_vintage: str | None) -> None:
    """Move the corpus files about to be replaced under snapshots/<old vintage>/."""
    dest = SNAPSHOTS_DIR / (old_vintage or "unknown")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for path in (SECTIONS_DIR, CHUNKS_FILE, MANIFEST_FILE, SOURCE_HASH_FILE):
        if path.exists():
            shutil.move(str(path), dest / path.name)
    log.info("Previous corpus kept in %s", dest)


def record_changes(diff: dict, path: Path | None = None) -> None:
    """Prepend this refresh's section changes to backend/code_changes.json."""
    path = path or CHANGES_FILE
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {"refreshes": []}
    data["refreshes"].insert(0, {
        "from": diff["old_vintage"],
        "to": diff["new_vintage"],
        "applied_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "added": diff["added"],
        "modified": diff["modified"],
        "removed": diff["deleted"],
    })
    path.write_text(json.dumps(data, indent=2) + "\n")


def promote(source: Path, diff: dict, new_manifest: dict, collection: str, client) -> dict:
    from .push_index import switch_alias

    same_vintage = diff["old_vintage"] == diff["new_vintage"]
    if same_vintage:
        shutil.rmtree(SECTIONS_DIR, ignore_errors=True)
    else:
        _snapshot_current(diff["old_vintage"])
    SECTIONS_NEW.rename(SECTIONS_DIR)
    CHUNKS_NEW.replace(CHUNKS_FILE)
    save_manifest(new_manifest, MANIFEST_FILE)
    save_hash(source)
    previous = switch_alias(client, collection, CODE_ALIAS)
    log.info("Local %s: %s -> %s", CODE_ALIAS, previous, collection)
    vintage = write_code_vintage(
        source, chunk_count=sum(e.chunk_count for e in new_manifest.values()),
        collection=collection, out=VINTAGE_FILE,
    )
    if not same_vintage or diff["added"] or diff["modified"] or diff["deleted"]:
        record_changes(diff)
    return vintage


def run(source: Path, *, dry_run: bool = False, full: bool = False, force: bool = False,
        client=None, model=None) -> int:
    diff, failures, new_manifest, new_vintage = stage(source)
    if dry_run:
        log.info("Dry run: nothing applied (staged in %s)", SECTIONS_NEW)
        return 2 if failures else 0
    if failures and not force:
        log.error("Stopping: %d abort gate(s) tripped. Fix the parser, or re-run with --force.", len(failures))
        return 1

    changes = len(diff["added"]) + len(diff["modified"]) + len(diff["deleted"])
    if diff["old_vintage"] == new_vintage and not changes and not full:
        log.info("Same vintage and no changes: nothing to embed")
        shutil.rmtree(SECTIONS_NEW, ignore_errors=True)
        CHUNKS_NEW.unlink(missing_ok=True)
        return 0

    from qdrant_client import QdrantClient

    from backend.config import get_settings

    from .push_index import alias_target

    settings = get_settings()
    if client is None:
        client = QdrantClient(url=settings.qdrant_url, timeout=120)
    if model is None:
        from sentence_transformers import SentenceTransformer

        log.info("Loading embedding model %s", settings.embedding_model)
        model = SentenceTransformer(settings.embedding_model)

    collection = collection_for(new_vintage)
    embed(client, model, diff, collection, alias_target(client, CODE_ALIAS), full=full)

    expected = _chunk_total(CHUNKS_NEW)
    got = client.count(collection, exact=True).count
    if got != expected:
        log.error("%s has %d points but %d chunks were staged; nothing promoted", collection, got, expected)
        return 1

    vintage = promote(source, diff, new_manifest, collection, client)
    log.info("Update complete: %s (%d chunks) in %s", vintage["label"], expected, collection)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=SOURCE_HTML, help="The American Legal HTML export")
    parser.add_argument("--dry-run", action="store_true", help="Parse and diff only; touch nothing else")
    parser.add_argument("--full", action="store_true", help="Re-embed every chunk into a fresh collection")
    parser.add_argument("--force", action="store_true", help="Apply even if an abort gate tripped")
    parser.add_argument("--manifest", action="store_true", help="Just build and save manifest")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.manifest:
        if not SECTIONS_DIR.exists():
            raise SystemExit(f"No sections directory at {SECTIONS_DIR}")
        manifest = build_manifest(SECTIONS_DIR)
        if CHUNKS_FILE.exists():
            set_chunk_counts(manifest, CHUNKS_FILE)
        save_manifest(manifest)
        # Record the source-HTML baseline too, so `python -m ingestion.source_check`
        # can report unchanged/updated instead of "unknown" (its own message points
        # users at `--manifest` for exactly this).
        save_hash()
        log.info("Saved manifest with %d sections to %s", len(manifest), MANIFEST_FILE)
        return

    if not args.source.exists():
        raise SystemExit(
            f"Source HTML not found at {args.source}. "
            "Download from American Legal Publishing first."
        )
    raise SystemExit(run(args.source, dry_run=args.dry_run, full=args.full, force=args.force))


if __name__ == "__main__":
    main()
