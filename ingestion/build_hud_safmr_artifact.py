"""Build ``hud_safmr.json``: HUD's Small Area Fair Market Rents by ZIP for the Chicago metro area.

WS4 PR5 (decision Item 69).  HUD sets a Fair Market Rent for every ZIP code in the Chicago-Joliet-Naperville
HUD Metro FMR Area, by bedroom count (studio to 4 bedrooms), and says that every Housing Choice Voucher program
in the area uses these ZIP-level figures.  The Chicago Housing Authority sets its voucher payment standards from
them; CHA's participant guide (June 2025) publishes no table of its own.  So the figure is HUD's: a benchmark
for what a voucher will pay toward rent plus utilities in that ZIP, never an asking or market rent.

The source is HUD's FMR Documentation System page for the area.  huduser.gov answers scripted requests with an
empty 202, so the table is copied from the page in a browser into a TSV (``zip`` then ``br0``..``br4``, ``#``
comment lines carrying the provenance), and this script turns that TSV into the committed artifact.

Usage:  PYTHONPATH=. python -m ingestion.build_hud_safmr_artifact --source <tsv> --fy 2027 --retrieved 2026-11-04
Production never runs this; it reads the committed artifact.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "ingestion" / "data" / "hud_safmr.json"
META_PATH = OUTPUT_PATH.with_name("hud_safmr.meta.json")
AREA = "Chicago-Joliet-Naperville, IL HUD Metro FMR Area"
SOURCE_URL = "https://www.huduser.gov/portal/datasets/fmr.html"  # the FMR datasets page; the ZIP table is its Small Area FMR view for the area
BEDROOMS = ("0", "1", "2", "3", "4")


def parse_tsv(text: str) -> dict[str, list[int]]:
    """ZIP → [studio, 1, 2, 3, 4 bedroom] monthly dollars. Raises ValueError on any malformed row: a partial
    table would read as "HUD lists no figure" for the ZIPs it lost."""
    zips: dict[str, list[int]] = {}
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.startswith("#") or line.startswith("zip"):
            continue
        cells = line.split("\t")
        if len(cells) != 6 or not re.fullmatch(r"\d{5}", cells[0]):
            raise ValueError(f"line {n}: expected a ZIP and five amounts, got {line!r}")
        amounts = [int(c.replace("$", "").replace(",", "")) for c in cells[1:]]
        if any(a <= 0 for a in amounts) or amounts != sorted(amounts):
            raise ValueError(f"line {n}: amounts must be positive and rise with bedrooms: {amounts}")
        if cells[0] in zips:
            raise ValueError(f"line {n}: ZIP {cells[0]} listed twice")
        zips[cells[0]] = amounts
    if len(zips) < 300:
        raise ValueError(f"only {len(zips)} ZIPs: the copied table looks incomplete")
    return zips


def build(source: Path, fy: int, retrieved: str) -> dict:
    zips = parse_tsv(source.read_text(encoding="utf-8"))
    return {
        "fy": fy,
        "area": AREA,
        "source": "HUD User, FMR Documentation System: Small Area Fair Market Rents",
        "source_url": SOURCE_URL,
        "retrieved": retrieved,
        "bedrooms": list(BEDROOMS),
        "zips": dict(sorted(zips.items())),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--fy", type=int, required=True)
    ap.add_argument("--retrieved", required=True, help="date the table was copied, YYYY-MM-DD")
    args = ap.parse_args()
    art = build(args.source, args.fy, args.retrieved)
    OUTPUT_PATH.write_text(json.dumps(art, indent=1) + "\n", encoding="utf-8")
    META_PATH.write_text(json.dumps({
        "builder": "ingestion/build_hud_safmr_artifact.py",
        "built_at": date.today().isoformat(),
        "fy": art["fy"],
        "retrieved": art["retrieved"],
        "zips": len(art["zips"]),
    }, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.name}: FY{art['fy']}, {len(art['zips'])} ZIPs")


if __name__ == "__main__":
    main()
