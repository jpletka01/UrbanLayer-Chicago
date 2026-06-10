"""Section manifest for tracking content changes across ingestion runs.

Computes a content hash per section (body_paragraphs + tables) so incremental
re-embedding only touches sections whose content actually changed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


MANIFEST_FILE = Path(__file__).resolve().parent / "data" / "manifest.json"


@dataclass
class SectionEntry:
    content_hash: str
    chunk_count: int
    title_number: int | None


@dataclass
class ManifestDiff:
    added: list[str]
    modified: list[str]
    deleted: list[str]

    @property
    def total_changes(self) -> int:
        return len(self.added) + len(self.modified) + len(self.deleted)


def _content_hash(section_data: dict) -> str:
    body = section_data.get("body_paragraphs", [])
    tables = section_data.get("tables", [])
    payload = json.dumps({"body_paragraphs": body, "tables": tables}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_manifest(sections_dir: Path) -> dict[str, SectionEntry]:
    manifest: dict[str, SectionEntry] = {}
    for path in sorted(sections_dir.glob("*.json")):
        data = json.loads(path.read_text())
        section_id = data.get("section", path.stem)
        manifest[section_id] = SectionEntry(
            content_hash=_content_hash(data),
            chunk_count=0,
            title_number=data.get("title_number"),
        )
    return manifest


def set_chunk_counts(manifest: dict[str, SectionEntry], chunks_file: Path) -> None:
    counts: dict[str, int] = {}
    with chunks_file.open() as fh:
        for line in fh:
            chunk = json.loads(line)
            sid = chunk.get("section", "")
            counts[sid] = counts.get(sid, 0) + 1
    for sid, entry in manifest.items():
        entry.chunk_count = counts.get(sid, 0)


def diff_manifests(
    old: dict[str, SectionEntry], new: dict[str, SectionEntry]
) -> ManifestDiff:
    old_ids = set(old)
    new_ids = set(new)
    added = sorted(new_ids - old_ids)
    deleted = sorted(old_ids - new_ids)
    modified = sorted(
        sid
        for sid in old_ids & new_ids
        if old[sid].content_hash != new[sid].content_hash
    )
    return ManifestDiff(added=added, modified=modified, deleted=deleted)


def save_manifest(manifest: dict[str, SectionEntry], path: Path | None = None) -> None:
    path = path or MANIFEST_FILE
    data = {
        sid: {
            "content_hash": e.content_hash,
            "chunk_count": e.chunk_count,
            "title_number": e.title_number,
        }
        for sid, e in sorted(manifest.items())
    }
    path.write_text(json.dumps(data, indent=2) + "\n")


def load_manifest(path: Path | None = None) -> dict[str, SectionEntry]:
    path = path or MANIFEST_FILE
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {
        sid: SectionEntry(
            content_hash=entry["content_hash"],
            chunk_count=entry.get("chunk_count", 0),
            title_number=entry.get("title_number"),
        )
        for sid, entry in data.items()
    }
