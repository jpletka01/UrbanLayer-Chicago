"""What a new code export changes, written before anything is applied.

``ingestion.update`` parses a new export into ``sections.new/`` and calls
:func:`build_diff` against the live ``sections/``. The result goes to
``ingestion/data/diff/<new vintage>/`` as ``diff.json`` and ``report.md``:

- per-title section counts, old -> new;
- added / modified / deleted section ids;
- a unified text diff of every modified section the product leans on (Title 17,
  Title 14, chapters 2-44 and 2-120);
- the ``Coun. J.`` dates in each modified section's legislative history, with the
  ones new to this export marked.

:func:`gate_failures` lists the reasons to stop before embedding (a parser that
silently lost a title has happened before: Title 14 was once dropped wholesale).
"""

from __future__ import annotations

import difflib
import json
from datetime import datetime, timezone
from pathlib import Path

from .chunk import _body_with_tables
from .manifest import SectionEntry, diff_manifests

# A title may lose this share of its sections before the refresh stops for a look.
MAX_TITLE_LOSS = 0.02
# Chapters outside Title 17/14 whose text the product cites.
CITED_CHAPTERS = ("2-44-", "2-120-")


def _load(sections_dir: Path, section_id: str) -> dict | None:
    path = sections_dir / f"{section_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _text(sec: dict) -> str:
    title = (sec.get("section_title") or "").strip()
    return f"§ {sec['section']} {title}\n" + _body_with_tables(sec)


def _in_text_diff_scope(section_id: str, title_number: int | None) -> bool:
    return title_number in (14, 17) or section_id.startswith(CITED_CHAPTERS)


def _title_counts(manifest: dict[str, SectionEntry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in manifest.values():
        key = str(entry.title_number) if entry.title_number is not None else "none"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _empty_title17(sections_dir: Path, manifest: dict[str, SectionEntry]) -> set[str]:
    out = set()
    for sid, entry in manifest.items():
        if entry.title_number != 17:
            continue
        sec = _load(sections_dir, sid) or {}
        if not any(p.strip() for p in sec.get("body_paragraphs", [])) and not sec.get("tables"):
            out.add(sid)
    return out


def build_diff(
    old_dir: Path,
    new_dir: Path,
    old_manifest: dict[str, SectionEntry],
    new_manifest: dict[str, SectionEntry],
    *,
    old_vintage: str | None,
    new_vintage: str,
) -> dict:
    d = diff_manifests(old_manifest, new_manifest)
    old_counts, new_counts = _title_counts(old_manifest), _title_counts(new_manifest)

    modified_detail = []
    for sid in d.modified:
        old, new = _load(old_dir, sid), _load(new_dir, sid)
        if old is None or new is None:
            # The old file can be missing locally; the manifest still knows it changed.
            modified_detail.append({"section": sid, "text_diff": None, "coun_j_dates": [], "new_coun_j_dates": []})
            continue
        old_dates, new_dates = old.get("effective_dates", []), new.get("effective_dates", [])
        text_diff = None
        if _in_text_diff_scope(sid, new.get("title_number")):
            text_diff = "\n".join(
                difflib.unified_diff(
                    _text(old).splitlines(), _text(new).splitlines(),
                    fromfile=f"{sid} ({old_vintage})", tofile=f"{sid} ({new_vintage})", lineterm="",
                )
            )
        modified_detail.append({
            "section": sid,
            "title_number": new.get("title_number"),
            "title_changed": (old.get("section_title") or "") != (new.get("section_title") or ""),
            "text_diff": text_diff,
            "coun_j_dates": new_dates,
            "new_coun_j_dates": [x for x in new_dates if x not in old_dates],
        })

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "old_vintage": old_vintage,
        "new_vintage": new_vintage,
        "sections": {"old": len(old_manifest), "new": len(new_manifest)},
        "chunks": {
            "old": sum(e.chunk_count for e in old_manifest.values()),
            "new": sum(e.chunk_count for e in new_manifest.values()),
        },
        "by_title": {
            t: {"old": old_counts.get(t, 0), "new": new_counts.get(t, 0)}
            for t in sorted(set(old_counts) | set(new_counts), key=lambda t: (not t.isdigit(), int(t) if t.isdigit() else 0))
        },
        "added": d.added,
        "modified": d.modified,
        "deleted": d.deleted,
        "modified_detail": modified_detail,
        "new_empty_title17": sorted(_empty_title17(new_dir, new_manifest) - _empty_title17(old_dir, old_manifest)),
    }


def gate_failures(diff: dict) -> list[str]:
    """Reasons to stop before embedding; empty when the export looks sane."""
    failures: list[str] = []
    if not any(c["old"] for c in diff["by_title"].values()):
        return failures  # first ingest: nothing to compare against
    old_v, new_v = diff["old_vintage"], diff["new_vintage"]
    if old_v and new_v < old_v:
        failures.append(f"vintage goes backwards: {old_v} -> {new_v}")
    for title, c in diff["by_title"].items():
        if c["old"] and not c["new"]:
            failures.append(f"Title {title} disappeared ({c['old']} sections)")
        elif not c["old"] and c["new"]:
            failures.append(f"Title {title} is new ({c['new']} sections): check the parse before trusting it")
        elif c["old"] and (c["old"] - c["new"]) / c["old"] > MAX_TITLE_LOSS:
            failures.append(f"Title {title} lost {c['old'] - c['new']} of {c['old']} sections (> {MAX_TITLE_LOSS:.0%})")
    t17 = diff["by_title"].get("17")
    if t17 and t17["new"] < t17["old"]:
        failures.append(f"Title 17 section count dropped: {t17['old']} -> {t17['new']}")
    if diff["new_empty_title17"]:
        failures.append(f"new empty-body Title 17 sections: {', '.join(diff['new_empty_title17'][:10])}")
    return failures


def render_markdown(diff: dict, failures: list[str]) -> str:
    lines = [
        f"# Code export diff: {diff['old_vintage']} -> {diff['new_vintage']}",
        "",
        f"Generated {diff['generated_at']}. Sections {diff['sections']['old']} -> {diff['sections']['new']}, "
        f"chunks {diff['chunks']['old']} -> {diff['chunks']['new']}.",
        "",
        f"**{len(diff['added'])} added, {len(diff['modified'])} modified, {len(diff['deleted'])} deleted.**",
        "",
        "## Abort gates",
        "",
    ]
    lines += [f"- FAIL: {f}" for f in failures] or ["- all passed"]
    if diff["old_vintage"] == diff["new_vintage"]:
        lines += ["", "Same vintage as the index: this is a re-parse of the same export, not a refresh."]
    lines += ["", "## Sections per title", "", "| Title | Old | New |", "|---|---|---|"]
    for t, c in diff["by_title"].items():
        mark = "" if c["old"] == c["new"] else " ←"
        lines.append(f"| {t} | {c['old']} | {c['new']}{mark} |")
    for name in ("added", "deleted"):
        lines += ["", f"## {name.capitalize()} ({len(diff[name])})", ""]
        lines += [f"- {sid}" for sid in diff[name]] or ["(none)"]
    lines += ["", f"## Modified ({len(diff['modified'])})", ""]
    for m in diff["modified_detail"]:
        dates = ", ".join(
            f"**{x}**" if x in m["new_coun_j_dates"] else x for x in m["coun_j_dates"]
        ) or "none"
        retitled = " (retitled)" if m.get("title_changed") else ""
        lines.append(f"### {m['section']}{retitled}")
        lines.append(f"Coun. J. dates (new in bold): {dates}")
        if m["text_diff"]:
            lines += ["", "```diff", m["text_diff"], "```"]
        lines.append("")
    return "\n".join(lines) + "\n"


def write_report(diff: dict, failures: list[str], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "diff.json").write_text(json.dumps({**diff, "gate_failures": failures}, indent=2) + "\n")
    report = out_dir / "report.md"
    report.write_text(render_markdown(diff, failures))
    return report
