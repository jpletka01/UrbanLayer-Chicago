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

    PYTHONPATH=. python -m eval.filing_panel [--split train|held_out|all] [--out eval/results/filing_panel.json]

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


def split_for(record_number: str) -> str:
    """Fixed before labelling and independent of which packets survive screening:
    a record is held out when its SHA-256 (first 8 hex digits) is divisible by 3."""
    return "held_out" if int(hashlib.sha256(record_number.encode()).hexdigest()[:8], 16) % 3 == 0 else "train"


def _expected(row: dict) -> dict[str, fe.FieldValue]:
    return {field_id: fe.FieldValue(v["value"], v["page"], v.get("unit"), v["source"])
            for field_id, v in row["labels"].items()}


def run(panel: dict, *, split: str = "all", private: Path = PRIVATE) -> dict:
    rows = [r for r in panel["rows"] if split == "all" or r["split"] == split]
    scores: dict[str, list[fe.Evaluation]] = {"train": [], "held_out": []}
    per_field: dict[str, Counter] = {}
    results = []
    for row in rows:
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
        scores[row["split"]].append(score)
        for field_id in set(expected) | set(emitted):
            c = per_field.setdefault(field_id, Counter())
            label, got = expected.get(field_id), emitted.get(field_id)
            c["expected"] += label is not None
            c["emitted"] += got is not None
            c["matched"] += label is not None and got == label
        results.append({
            "record_number": row["record_number"], "split": row["split"], "label_status": row["label_status"],
            "expected": score.expected, "emitted": score.emitted, "matched": score.matched,
            "wrong_value": score.wrong_value, "wrong_page": score.wrong_page, "wrong_unit": score.wrong_unit,
            "mismatches": sorted(k for k, v in emitted.items() if expected.get(k) != v),
            "missed": sorted(k for k in expected if k not in emitted), "problems": problems,
        })
    summary = {name: _aggregate(s) for name, s in scores.items() if s}
    held = scores["held_out"]
    verified = all(r["label_status"] == "human_verified" for r in panel["rows"])
    measured = fe.panel_passes(held, panel_size=len(panel["rows"]), held_out_size=len(held)) if split == "all" else None
    spent = panel.get("held_out_scored_with")
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
        "reader_version": filing_reader.READER_VERSION, "panel_rows": len(panel["rows"]), "split": split,
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
    args = parser.parse_args(argv)
    result = run(json.loads(PANEL.read_text()), split=args.split)
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.write_text(text + "\n")
    print(json.dumps({k: result[k] for k in ("reader_version", "panel_rows", "split", "labels_human_verified",
                                              "gate", "summary", "per_field")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
