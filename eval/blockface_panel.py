"""WS5 PR4 (measurement only): could the RS-3 "60% of the block face" test be computed from official records?

§17-2-0303-B.1 lets an RS-3 two-unit building use 1,500 sq ft of lot per unit when the parcel is in the
Predominance of the Block (606) district OR when 60% or more of the lots on its block face already hold two or
more units.  The first trigger ships in WS5 PR1.  This script measures whether the second could be computed
honestly, before any product promises it.  No model; nothing is served.

For a fixed, seeded panel of RS-3 block faces from a Discovery index:

1. **Block face.** Base parcels (PIN suffix 0000) in a residential district whose FAR is 0.9 (RS-3 is the only
   residential district at 0.9 in the table), keyed by (street direction, street name, hundred block, side by
   address parity) from the index's Assessor address.  This approximates "the same street segment between cross
   streets, same side": Chicago's hundred blocks usually are one block face, but not always.  Parcels with an
   approximate address (the builder's ``~`` tier) are left out and counted.
2. **Units per lot, from an official record only.**  The Assessor's residential characteristics (``x54s-btds``,
   the newest year per PIN): ``char_apts`` "Two".."Six" = that many units (2+); "None" on a single-card parcel =
   one dwelling; a multi-card parcel (a second building, often a coach house) = unknown.  From the class alone:
   2-99 (condominium building) and 3-xx (7+ units) = 2+; 1-xx (vacant) = 0.  Anything else is unknown.
3. **The gate (Jack, 2026-10-31):** a block face is computable only when at least ``THRESHOLD`` (90%) of its lots
   have a unit count from an official record.  For a computable face, the rule is met when 60% or more of its
   lots hold 2+ units.

Usage:  PYTHONPATH=. python -m eval.blockface_panel --index <discovery_index.db> [--faces 200] [--seed 31] \
            [--out eval/results/2026-10-31-ws5/blockface_panel.json]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import httpx

THRESHOLD = 0.90
RULE_SHARE = 0.60
RS3_FAR = 0.9
MIN_LOTS = 4  # a face with fewer lots is too small to say "60% of the block face"
CHARACTERISTICS = "https://datacatalog.cookcountyil.gov/resource/x54s-btds.json"
PIN_BATCH = 300

_WORDS = {"None": 0, "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5, "Six": 6}
_ADDRESS = re.compile(r"^(\d+)\s+([NSEW])\s+(.+?)\s*$")


def face_key(address: str | None) -> tuple[str, str, int, str] | None:
    """("N", "KEDZIE AVE", 1700, "odd") for "1747 N KEDZIE AVE"; None for an approximate or unparsable address."""
    if not address or address.startswith("~"):
        return None
    m = _ADDRESS.match(address.strip().upper())
    if not m:
        return None
    number = int(m.group(1))
    return m.group(2), m.group(3), number // 100 * 100, "odd" if number % 2 else "even"


def units_from_record(cls: str | None, chars: dict | None) -> tuple[int | None, str]:
    """(units or None, the reason).  ``units`` is 2 for "two or more" from a class, else the recorded count."""
    c = (cls or "").replace("-", "")
    if chars is not None:
        apts = chars.get("char_apts")
        cards = int(float(chars.get("pin_num_cards") or 1))
        if apts in _WORDS and apts != "None":
            return _WORDS[apts], "char_apts"
        if apts == "None":
            return (1, "char_apts_none") if cards <= 1 else (None, "multi_card")
        return None, "char_apts_missing"
    if c == "299" or c.startswith("3"):
        return 2, "class_multi_unit"
    if c.startswith("1"):
        return 0, "class_vacant"
    return None, "no_record"


def judge_face(lots: list[int | None]) -> dict:
    n = len(lots)
    known = [u for u in lots if u is not None]
    coverage = len(known) / n if n else 0.0
    computable = coverage >= THRESHOLD
    two_plus = sum(1 for u in known if u >= 2)
    share = two_plus / n if n else 0.0
    return {
        "lots": n, "known": len(known), "coverage": round(coverage, 4), "computable": computable,
        "two_plus": two_plus, "two_plus_share": round(share, 4),
        # Unknown lots are counted as NOT 2+ here, so "meets" is a lower bound; only a computable face is judged.
        "meets_60": (share >= RULE_SHARE) if computable else None,
    }


def rs3_faces(index: Path) -> tuple[dict, Counter]:
    con = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    faces: dict = defaultdict(list)
    skipped: Counter = Counter()
    for pin, attrs_json in con.execute("select pin, attrs from parcels where pin like '%-0000'"):
        a = json.loads(attrs_json)
        if a.get("zoning_group") != "residential" or a.get("density_band") != RS3_FAR:
            continue
        key = face_key(a.get("address"))
        if key is None:
            skipped["approximate_or_unparsed_address"] += 1
            continue
        faces[key].append((pin, a.get("class")))
    return faces, skipped


def fetch_characteristics(pins: list[str]) -> dict[str, dict]:
    """Newest characteristics row per PIN14 (undashed key).  Raises on a failed request: a failure is never 'no record'."""
    out: dict[str, dict] = {}
    plain = sorted({p.replace("-", "") for p in pins})
    with httpx.Client(timeout=httpx.Timeout(90.0)) as client:
        for i in range(0, len(plain), PIN_BATCH):
            chunk = plain[i:i + PIN_BATCH]
            resp = client.get(CHARACTERISTICS, params={
                "$select": "pin,year,char_apts,pin_num_cards,class",
                "$where": f"pin in ({','.join(repr(p) for p in chunk)})",
                "$order": "year DESC", "$limit": "50000"})
            resp.raise_for_status()
            for row in resp.json():
                out.setdefault(row["pin"], row)  # year DESC: the first row per PIN is the newest
    return out


def run(index: Path, n_faces: int, seed: int) -> dict:
    faces, skipped = rs3_faces(index)
    eligible = sorted(k for k, v in faces.items() if len(v) >= MIN_LOTS)
    sample = random.Random(seed).sample(eligible, min(n_faces, len(eligible)))
    pins = [p for k in sample for p, _ in faces[k]]
    chars = fetch_characteristics(pins)
    reasons: Counter = Counter()
    rows = []
    for key in sample:
        units = []
        for pin, cls in faces[key]:
            u, why = units_from_record(cls, chars.get(pin.replace("-", "")))
            reasons[why] += 1
            units.append(u)
        rows.append({"face": " ".join(map(str, key)), **judge_face(units)})
    computable = [r for r in rows if r["computable"]]
    return {
        "index_faces": len(faces), "eligible_faces": len(eligible), "sampled": len(rows), "seed": seed,
        "threshold": THRESHOLD, "skipped_lots": dict(skipped),
        "lots": sum(r["lots"] for r in rows), "lot_reasons": dict(reasons.most_common()),
        "lot_coverage": round(sum(r["known"] for r in rows) / max(1, sum(r["lots"] for r in rows)), 4),
        "computable_faces": len(computable),
        "computable_share": round(len(computable) / len(rows), 4) if rows else 0.0,
        "meets_60_of_computable": sum(1 for r in computable if r["meets_60"]),
        "faces": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--faces", type=int, default=200)
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    result = run(args.index, args.faces, args.seed)
    print(f"RS-3 block faces in the index: {result['index_faces']} ({result['eligible_faces']} with {MIN_LOTS}+ lots); "
          f"sampled {result['sampled']} faces, {result['lots']} lots")
    print(f"lot coverage from an official record: {result['lot_coverage']:.1%}; reasons {result['lot_reasons']}")
    print(f"computable faces (>= {THRESHOLD:.0%} of lots known): {result['computable_faces']} ({result['computable_share']:.1%}); "
          f"of those meeting the 60% rule: {result['meets_60_of_computable']}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=1, sort_keys=True))
        print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
