"""Unified update CLI for the ingestion pipeline.

Usage:
    python -m ingestion.update                # incremental: parse -> chunk -> diff -> embed changed
    python -m ingestion.update --dry-run      # show what would change without modifying Qdrant
    python -m ingestion.update --full         # full rebuild (parse -> chunk -> embed all)
    python -m ingestion.update --manifest     # just build/save manifest from current sections
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from .manifest import (
    MANIFEST_FILE,
    build_manifest,
    diff_manifests,
    load_manifest,
    save_manifest,
    set_chunk_counts,
)


log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
SECTIONS_DIR = DATA_DIR / "sections"
CHUNKS_FILE = DATA_DIR / "chunks.jsonl"
SOURCE_HTML = DATA_DIR / "chicago-il-codes.html"


def _run_step(description: str, cmd: list[str]) -> None:
    log.info("Step: %s", description)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("Failed: %s\n%s", description, result.stderr)
        raise SystemExit(1)
    if result.stdout.strip():
        for line in result.stdout.strip().split("\n")[-5:]:
            log.info("  %s", line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show diff without modifying Qdrant")
    parser.add_argument("--full", action="store_true", help="Full rebuild instead of incremental")
    parser.add_argument("--manifest", action="store_true", help="Just build and save manifest")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.manifest:
        if not SECTIONS_DIR.exists():
            raise SystemExit(f"No sections directory at {SECTIONS_DIR}")
        manifest = build_manifest(SECTIONS_DIR)
        if CHUNKS_FILE.exists():
            set_chunk_counts(manifest, CHUNKS_FILE)
        save_manifest(manifest)
        log.info("Saved manifest with %d sections to %s", len(manifest), MANIFEST_FILE)
        return

    if not SOURCE_HTML.exists():
        raise SystemExit(
            f"Source HTML not found at {SOURCE_HTML}. "
            "Download from American Legal Publishing first."
        )

    _run_step(
        "Parse HTML into sections",
        [sys.executable, "-m", "ingestion.parse_chicago_code"],
    )
    _run_step(
        "Chunk sections",
        [sys.executable, "-m", "ingestion.chunk"],
    )

    new_manifest = build_manifest(SECTIONS_DIR)
    set_chunk_counts(new_manifest, CHUNKS_FILE)
    old_manifest = load_manifest()

    if old_manifest and not args.full:
        diff = diff_manifests(old_manifest, new_manifest)
        log.info(
            "Diff: %d added, %d modified, %d deleted (out of %d total sections)",
            len(diff.added),
            len(diff.modified),
            len(diff.deleted),
            len(new_manifest),
        )
        if diff.added:
            log.info("  Added: %s", ", ".join(diff.added[:10]) + ("..." if len(diff.added) > 10 else ""))
        if diff.modified:
            log.info("  Modified: %s", ", ".join(diff.modified[:10]) + ("..." if len(diff.modified) > 10 else ""))
        if diff.deleted:
            log.info("  Deleted: %s", ", ".join(diff.deleted[:10]) + ("..." if len(diff.deleted) > 10 else ""))

        if args.dry_run:
            log.info("Dry run -- no changes applied")
            return

        if diff.total_changes == 0:
            log.info("No changes -- saving manifest and exiting")
            save_manifest(new_manifest)
            return

        _run_step(
            "Incremental embed",
            [sys.executable, "-m", "ingestion.embed_and_store", "--incremental"],
        )
    else:
        if args.dry_run:
            log.info("Dry run -- would do full rebuild (%d sections, %d chunks)",
                     len(new_manifest), sum(e.chunk_count for e in new_manifest.values()))
            return

        embed_args = [sys.executable, "-m", "ingestion.embed_and_store"]
        if args.full or not old_manifest:
            embed_args.append("--recreate")
        _run_step("Full embed", embed_args)

    log.info("Update complete")


if __name__ == "__main__":
    main()
