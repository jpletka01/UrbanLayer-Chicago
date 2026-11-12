"""Held-out accuracy panel for the WS2 PR4 offline Type 1 filing reader (decision Item 70).

Labels live in ``eval/filing_panel.json``: matter/attachment identity, SHA-256,
and the expected value, unit, attachment and page for each field.  No PDF or
OCR text is committed; the PDFs are read from the ignored private directory
the reader's downloader fills (``research/pending-filing-pdfs/panel``).

The split is fixed by a hash of the record number before any label is written
(``split_for``; a test checks every row's stored split against it).  The parser is developed against ``train`` rows only; the
``held_out`` rows are scored once: ``held_out_scored_with`` in the panel names
the reader version that spent them, and any later version reports ``post_hoc``.  The gate is
``filing_evaluation.panel_passes`` on the held-out rows, and it can only
*pass* when every panel row is ``human_verified``.  Rows labelled by the
assistant are ``assistant_draft``: the result is then reported as
``provisional``, never as a pass.

    PYTHONPATH=. python -m eval.filing_panel [--fresh | --fresh-panel FILE] [--split train|held_out|all] [--out FILE]

Offline, no model call, no network.  Needs Poppler/Tesseract and ``pypdf`` (requirements-dev.txt).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from backend.legislation import filing_evaluation as fe
from backend.legislation import filing_reader

PANEL = Path(__file__).resolve().parent / "filing_panel.json"
PRIVATE = Path(__file__).resolve().parent.parent / "research" / "pending-filing-pdfs" / "panel"
# The fresh held-out set (historical passed Type 1 filings): with it, every row above is development data.
FRESH = Path(__file__).resolve().parent / "filing_panel_historical.json"
FRESH_PRIVATE = PRIVATE.parent / "historical"


def split_for(record_number: str) -> str:
    """Fixed before labelling and independent of which packets survive screening:
    a record is held out when its SHA-256 (first 8 hex digits) is divisible by 3."""
    return "held_out" if int(hashlib.sha256(record_number.encode()).hexdigest()[:8], 16) % 3 == 0 else "train"


def _expected(row: dict) -> dict[str, fe.FieldValue]:
    return {field_id: fe.FieldValue(v["value"], v["page"], v.get("unit"), v["source"])
            for field_id, v in row["labels"].items()}


def run(panel: dict, *, split: str = "all", private: Path = PRIVATE,
        fresh: dict | None = None, fresh_private: Path = FRESH_PRIVATE) -> dict:
    """Score the panel.  With ``fresh``, the main panel's rows are all ``train`` and the
    fresh panel's rows are the held-out set; its own ``held_out_scored_with`` spends it."""
    if fresh is None:
        tagged = [(r, r["split"], private) for r in panel["rows"]]
        spent = panel.get("held_out_scored_with")
    else:
        tagged = [(r, "train", Path(r["_private"]) if "_private" in r else private) for r in panel["rows"]]
        tagged += [(r, "held_out", fresh_private) for r in fresh["rows"]]
        spent = fresh.get("held_out_scored_with")
    all_rows = [r for r, _, _ in tagged]
    tagged = [t for t in tagged if split == "all" or t[1] == split]
    scores: dict[str, list[fe.Evaluation]] = {"train": [], "held_out": []}
    per_field: dict[str, Counter] = {}
    results = []
    for row, row_split, private in tagged:
        emitted: dict[str, fe.FieldValue] = {}
        problems = []
        for role, attachment in row["attachments"].items():
            path = private / row["record_number"] / f"{role}.pdf"
            if not path.exists():
                problems.append(f"{role}: private PDF missing")
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest() != attachment["sha256"]:
                problems.append(f"{role}: sha256 differs from the labelled copy")
                continue
            screens, fields = filing_reader.read_packet(path, role, cache_dir=path.parent / "ocr", title=row.get("title"))
            if any(s.status in {"eds", "unreadable"} for s in screens):
                problems.append(f"{role}: packet failed the page screen")
            for f in fields:
                emitted[f.id] = fe.FieldValue(f.value, f.page, f.unit, f.source)
        expected = _expected(row)
        score = fe.evaluate(expected, emitted)
        scores[row_split].append(score)
        for field_id in set(expected) | set(emitted):
            c = per_field.setdefault(field_id, Counter())
            label, got = expected.get(field_id), emitted.get(field_id)
            c["expected"] += label is not None
            c["emitted"] += got is not None
            c["matched"] += label is not None and got == label
        results.append({
            "record_number": row["record_number"], "split": row_split, "label_status": row["label_status"],
            "expected": score.expected, "emitted": score.emitted, "matched": score.matched,
            "wrong_value": score.wrong_value, "wrong_page": score.wrong_page, "wrong_unit": score.wrong_unit,
            "mismatches": sorted(k for k, v in emitted.items() if expected.get(k) != v),
            "missed": sorted(k for k in expected if k not in emitted), "problems": problems,
        })
    summary = {name: _aggregate(s) for name, s in scores.items() if s}
    held = scores["held_out"]
    verified = all(r["label_status"] == "human_verified" for r in all_rows)
    measured = fe.panel_passes(held, panel_size=len(all_rows), held_out_size=len(held)) if split == "all" else None
    if measured is None:
        gate = "not_scored"
    elif spent and spent != filing_reader.READER_VERSION:
        # The held-out rows were already scored by an earlier reader version, and
        # what that run showed shaped this one: the number is informative, never a gate.
        gate = "post_hoc"
    elif not measured:
        gate = "fail"
    else:
        gate = "pass" if verified else "provisional"
    return {
        "reader_version": filing_reader.READER_VERSION, "panel_rows": len(all_rows), "split": split,
        "held_out_source": "historical" if fresh is not None else "panel",
        "labels_human_verified": verified, "gate": gate, "summary": summary,
        "per_field": {k: dict(v) for k, v in sorted(per_field.items())}, "rows": results,
    }


def _aggregate(scores: list[fe.Evaluation]) -> dict:
    total = fe.Evaluation(*(sum(getattr(s, k) for s in scores) for k in
                           ("expected", "emitted", "matched", "wrong_value", "wrong_page", "wrong_unit")))
    return {"rows": len(scores), "expected": total.expected, "emitted": total.emitted, "matched": total.matched,
            "precision": round(total.precision, 4), "recall": round(total.recall, 4),
            "wrong_value": total.wrong_value, "wrong_page": total.wrong_page, "wrong_unit": total.wrong_unit}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", choices=("train", "held_out", "all"), default="all")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--fresh", action="store_true", help=f"hold out {FRESH.name} instead of the panel's own split")
    parser.add_argument("--fresh-panel", type=Path, help="hold out this fresh panel file; earlier fresh panels become development rows")
    args = parser.parse_args(argv)
    panel = json.loads(PANEL.read_text())
    fresh, fresh_private = None, FRESH_PRIVATE
    if args.fresh_panel:
        # Every earlier, spent fresh set joins the development rows.
        for spent in sorted(PANEL.parent.glob("filing_panel_*.json")):
            extra = json.loads(spent.read_text())
            # Only a set already scored joins development; an unspent one stays sealed.
            if spent.resolve() != args.fresh_panel.resolve() and extra.get("held_out_scored_with"):
                base = PANEL.parent.parent / extra.get("private_dir", "research/pending-filing-pdfs/historical")
                panel = {**panel, "rows": panel["rows"] + [{**r, "_private": str(base)} for r in extra["rows"]]}
        fresh = json.loads(args.fresh_panel.read_text())
        if len(fresh["rows"]) < fe.MIN_HELD_OUT_ROWS:
            # Scoring spends a held-out set; a set too small to pass must not be spent.
            print(f"{args.fresh_panel.name}: {len(fresh['rows'])} rows; not scored until it has {fe.MIN_HELD_OUT_ROWS}", file=sys.stderr)
            return 2
        fresh_private = PANEL.parent.parent / fresh["private_dir"]
    elif args.fresh:
        fresh = json.loads(FRESH.read_text())
    result = run(panel, split=args.split, fresh=fresh, fresh_private=fresh_private)
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.write_text(text + "\n")
    print(json.dumps({k: result[k] for k in ("reader_version", "panel_rows", "split", "held_out_source", "labels_human_verified",
                                              "gate", "summary", "per_field")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
