"""Compare two versions of ``build_provenance`` on recorded Profile payloads (no network, no model).

Each ``P*.profile.json`` from a kit run carries the ``context``, ``zone_definition`` and
resolved parcel that ``/api/scorecard`` built its provenance from. This rebuilds the provenance
with the code at ``--base`` (a git ref; default ``main``) and with the working tree, using one
fixed query date, and reports per parcel what was added, removed or changed.

    PYTHONPATH=. python -m eval.provenance_diff eval/results/2026-10-21-m4/parcel_kit_raw

"Only added fields" means: no key removed, no existing key's value changed. A change that is
intended (a polygon-derived lot area is now ``derived``, not ``official_record``) is listed
under CHANGED so it is a decision in the PR, not a surprise. Exit code 1 when anything was
removed or changed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import types
from pathlib import Path

QUERY_DATE = "2026-10-21"


def _load_base(ref: str) -> types.ModuleType:
    src = subprocess.run(
        ["git", "show", f"{ref}:backend/provenance.py"], capture_output=True, text=True, check=True,
    ).stdout
    mod = types.ModuleType("provenance_base")
    mod.__package__ = "backend"
    exec(compile(src, f"{ref}:backend/provenance.py", "exec"), mod.__dict__)
    return mod


def _build(mod, payload: dict) -> dict:
    from backend.models import ContextObject

    ctx = ContextObject.model_validate(payload["context"])
    return mod.build_provenance(
        context=ctx, zone_definition=payload.get("zone_definition"),
        resolved_pin=payload.get("resolved_pin"), resolved_confidence=payload.get("resolved_confidence"),
        query_date=QUERY_DATE,
    )


def diff_maps(old: dict, new: dict) -> dict:
    out = {"added_entries": sorted(set(new) - set(old)), "removed_entries": sorted(set(old) - set(new)),
           "added_fields": {}, "removed_fields": {}, "changed": {}}
    for fact in sorted(set(old) & set(new)):
        o, n = old[fact], new[fact]
        added = sorted(set(n) - set(o))
        removed = sorted(set(o) - set(n))
        changed = {k: (o[k], n[k]) for k in sorted(set(o) & set(n)) if o[k] != n[k]}
        if added:
            out["added_fields"][fact] = added
        if removed:
            out["removed_fields"][fact] = removed
        if changed:
            out["changed"][fact] = changed
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw_dir", help="a kit run's parcel_kit_raw directory (P*.profile.json)")
    ap.add_argument("--base", default="main", help="git ref holding the old backend/provenance.py")
    ap.add_argument("--expect", action="append", default=[], metavar="FACT.FIELD",
                    help="an intended change (repeatable), e.g. property.land_sqft.kind; listed but not a failure")
    args = ap.parse_args(argv)

    base = _load_base(args.base)
    from backend import provenance as new

    files = sorted(Path(args.raw_dir).glob("P*.profile.json"), key=lambda p: int(p.name[1:].split(".")[0]))
    if not files:
        print(f"no P*.profile.json in {args.raw_dir}", file=sys.stderr)
        return 2
    bad = 0
    totals = {"parcels": 0, "entries": 0, "new_fields": set()}
    for f in files:
        payload = json.loads(f.read_text())
        old_map, new_map = _build(base, payload), _build(new, payload)
        d = diff_maps(old_map, new_map)
        totals["parcels"] += 1
        totals["entries"] += len(new_map)
        for fields in d["added_fields"].values():
            totals["new_fields"].update(fields)
        # the stored payload was built by deployed code; it should equal the base rebuild
        stored = payload.get("provenance")
        drift = "" if stored is None or stored == old_map else "  (stored payload differs from the base rebuild)"
        print(f"{f.name.split('.')[0]:>4}  {payload.get('address') or payload.get('resolved_pin')}: "
              f"{len(old_map)} entries -> {len(new_map)}{drift}")
        for fact, ch in list(d["changed"].items()):
            for k, (o, n) in list(ch.items()):
                if f"{fact}.{k}" in args.expect:
                    print(f"        expected {fact}.{k}: {o!r} -> {n!r}")
                    del ch[k]
                else:
                    print(f"        CHANGED {fact}.{k}: {o!r} -> {n!r}")
            if not ch:
                del d["changed"][fact]
        for fact, fields in d["removed_fields"].items():
            print(f"        REMOVED {fact}: {fields}")
        for e in d["removed_entries"]:
            print(f"        REMOVED ENTRY {e}")
        for e in d["added_entries"]:
            print(f"        ADDED ENTRY {e}")
        bad += bool(d["removed_entries"] or d["removed_fields"] or d["changed"] or d["added_entries"])
    print(f"\n{totals['parcels']} parcels, {totals['entries']} entries; new fields: {', '.join(sorted(totals['new_fields']))}")
    print("only added fields" if not bad else f"{bad} parcel(s) with removed or changed content (see above)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
