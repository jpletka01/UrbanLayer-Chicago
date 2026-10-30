# Property Profile: the use rules and the transit amount it was leaving out

Format: see `README.md` in this folder.

---

## Item 1: carry PR #54's code fix onto current main; leave its benchmark record behind (2026-10-30)

**Decision:** the code commit of #54 (written 2026-10-03, 235 commits behind main) is cherry-picked onto main as a new branch; the second commit, which recorded a live benchmark run, is not carried.

- **What the fix does.** The kit's only Profile misses were things it did not say: the DC-16 and B1-2 ground-floor housing rule (P8, P3), why M2-3 allows no housing (P10), and how far parking can drop in a transit-served district (P9, P5). `zoning_definitions.py` now states those rules, each pinned to the ingested use tables by `test_zoning_uses_text.py`; the regulatory card shows the `tod_benefits` note on the transit row; the dash-3 verdict reason states the amount (en/es).
- **Conflicts resolved.** Main had since added "no new gas stations, §17-3-0207" to the C1/C2 use text, added `designations` to the regulatory card and the Municipal Code refresh. The merged text keeps both: the ground-floor rule and the gas-station note; the card takes `designations` and `tod`.
- **Pin files checked.** The two section files the PR tracks (`17-4-0200`, `17-5-0200`) hash to the manifest entries of the current June 2026 export, so the pin test reads the text the app serves.
- **Why the benchmark commit is left out.** It records a live run at a commit that no longer exists, and `docs/benchmark/` was rewritten by the Code refresh since. Merging it would put a stale run beside newer data, and `results.json` is generated. Re-recording needs a fresh run (live services); that is a separate decision.

**Revisit if:** a new kit run is wanted. Run it on current main, then record it; the 2026-10-03 numbers (97% coverage, 100% on answered fields, 0 confident-wrong, in-sample) stay in PR #54's description.

**Numbers**
- **Before:** the Profile said "residential" only for DC-16 and "No residential" for M2-3.
- **After:** backend 2,482 passed (66 integration deselected); frontend 702 passed; `tsc -b` clean.
- **Not measured:** the benchmark score on current main.
- **Reproduce:** `python -m pytest backend/tests/test_zoning_uses_text.py -q`.
