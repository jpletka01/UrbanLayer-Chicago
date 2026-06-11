"""R7 acceptance audit — end-to-end exact-PIN rate for address resolution.

Pre-deploy gate for the R7 fix (truth-model §6, r7-implementation-plan §4/§9).

Method: sample real Chicago addresses from the authoritative Cook County Address
Points dataset (78yw-iddh), reconstruct each as a user would type it, run the
FULL production resolver (`_resolve_location(address=...)`), and compare the
resolved PIN to the authoritative PIN.

What this measures: the parse → query → match machinery of the new address→PIN
path across many real street formats (directions, suffixes, multi-word names) —
exactly where the `st_predir` word-vs-letter defect hid. It does NOT independently
measure dataset *coverage* (addresses absent from 78yw-iddh, e.g. new construction),
which is a separate, already-documented bounded limitation — those fall to the
flagged "approximate" path by design.

Target: >= 90% exact-PIN on the sample, plus the EX/control QA parcels.

Run (needs network to the Cook County portal):
    PYTHONPATH=. python -m eval.r7_audit            # default sample
    PYTHONPATH=. python -m eval.r7_audit --n 200
"""

import argparse
import asyncio
import sys

import httpx

from backend.config import get_settings
from backend.main import _resolve_location

PORTAL = "https://datacatalog.cookcountyil.gov/resource/78yw-iddh.json"

# Spelled-out predirectional -> single letter (parse_chicago_address yields letters).
_DIR_LETTER = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}

# Scatter across PIN township prefixes to diversify geography cheaply (deep
# Socrata $offset pagination times out). These 2-digit prefixes cover Chicago
# proper (Lake View, Jefferson, West/South Chicago, Hyde Park, Rogers Park, etc.).
_PIN_PREFIXES = ["10", "13", "14", "16", "17", "20", "25"]

# QA parcels (memory: EX subject + taxable control). Addresses reverse-looked-up.
_QA_PINS = ["14283190070000", "14331030110000"]


def _norm_pin(raw: str) -> str:
    return str(raw or "").replace("-", "").zfill(14)


def _reconstruct(row: dict) -> str | None:
    """Build a user-format address string from a 78yw-iddh row, or None if the
    row lacks the parts parse_chicago_address needs (number + direction + name)."""
    number = row.get("add_number")
    predir = row.get("st_predir")
    name = row.get("st_name")
    suffix = row.get("lst_type") or row.get("st_postyp")  # abbreviation preferred
    if not (number and predir and name):
        return None
    letter = _DIR_LETTER.get(str(predir).upper(), str(predir))
    parts = [str(number), letter, str(name).title()]
    if suffix:
        parts.append(str(suffix).title())
    return " ".join(parts)


async def _sample_rows(client: httpx.AsyncClient, n: int) -> list[dict]:
    per = max(1, n // len(_PIN_PREFIXES) + 1)
    rows: list[dict] = []
    for prefix in _PIN_PREFIXES:
        try:
            r = await client.get(PORTAL, params={
                "$select": "add_number,st_predir,st_name,st_postyp,lst_type,pin",
                "$where": (
                    "inc_muni='Chicago' AND st_predir IS NOT NULL "
                    f"AND starts_with(pin, '{prefix}')"
                ),
                "$order": "pin",
                "$limit": per,
            })
            r.raise_for_status()
            rows.extend(r.json())
        except Exception as exc:  # noqa: BLE001
            print(f"  (sample bucket {prefix} failed: {type(exc).__name__})")
    return rows[:n]


async def _address_for_pin(client: httpx.AsyncClient, pin: str) -> str | None:
    r = await client.get(PORTAL, params={
        "$select": "add_number,st_predir,st_name,st_postyp,lst_type,pin",
        "$where": f"pin='{pin}'",
        "$limit": 1,
    })
    r.raise_for_status()
    data = r.json()
    return _reconstruct(data[0]) if data else None


async def _resolve_one(address: str) -> tuple[str | None, str]:
    """Return (resolved_pin, confidence) for an address, ('ERROR:...', '') on failure."""
    try:
        rl = await _resolve_location(address=address)
        return rl.pin, rl.confidence
    except Exception as exc:  # noqa: BLE001
        return f"ERROR:{type(exc).__name__}", ""


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150, help="sample size")
    args = ap.parse_args()

    settings = get_settings()
    if not settings.address_point_resolution_enabled:
        print("WARNING: address_point_resolution_enabled is False — auditing the "
              "degraded path only.")

    async with httpx.AsyncClient(timeout=httpx.Timeout(25.0)) as client:
        rows = await _sample_rows(client, args.n)

        total = 0
        exact = 0
        authoritative = 0
        misses: list[tuple[str, str, str, str]] = []  # addr, truth, got, conf
        parse_skips = 0

        for row in rows:
            addr = _reconstruct(row)
            if not addr:
                parse_skips += 1
                continue
            truth = _norm_pin(row.get("pin"))
            got, conf = await _resolve_one(addr)
            total += 1
            if conf == "authoritative":
                authoritative += 1
            if got == truth:
                exact += 1
            else:
                misses.append((addr, truth, str(got), conf))

        # QA parcels
        qa_results = []
        for pin in _QA_PINS:
            addr = await _address_for_pin(client, pin)
            if not addr:
                qa_results.append((pin, None, "NO ADDRESS POINT", ""))
                continue
            got, conf = await _resolve_one(addr)
            qa_results.append((pin, addr, got, conf))

    rate = (exact / total * 100) if total else 0.0
    auth_rate = (authoritative / total * 100) if total else 0.0

    print("\n" + "=" * 64)
    print("R7 ACCEPTANCE AUDIT")
    print("=" * 64)
    print(f"Sampled rows:        {len(rows)}")
    print(f"Unparseable (skip):  {parse_skips}")
    print(f"Tested:              {total}")
    print(f"Exact-PIN match:     {exact}/{total}  ({rate:.1f}%)")
    print(f"Authoritative tier:  {authoritative}/{total}  ({auth_rate:.1f}%)")
    print(f"Target:              >= 90.0%   -> {'PASS' if rate >= 90 else 'FAIL'}")
    if misses:
        print(f"\nMisses ({len(misses)}):")
        for addr, truth, got, conf in misses[:25]:
            print(f"  {addr:<38} truth={truth} got={got} ({conf})")

    print("\nQA parcels:")
    qa_ok = True
    for pin, addr, got, conf in qa_results:
        if addr is None:
            # No address point exists for this parcel (coverage gap, e.g. exempt /
            # institutional). The address path correctly degrades to "approximate"
            # + INV-5 disclosure — not a resolver failure, so not a gate fail.
            status = "COVERAGE-GAP (no address point; degrades by design)"
        elif got == pin:
            status = "OK"
        else:
            status = "MISS (wrong PIN)"
            qa_ok = False
        print(f"  {pin}  addr={addr!r}  got={got} ({conf})  [{status}]")

    print("=" * 64)
    passed = rate >= 90 and qa_ok
    print("RESULT:", "PASS" if passed else "REVIEW")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
