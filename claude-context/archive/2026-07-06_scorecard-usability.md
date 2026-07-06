# Scorecard usability pass (2026-07-06) — SHIPPED (`main` 3c232ec + 62fe4cc)

Jack's 5-item usability review → one branch, all five fixed, prod-deployed same day.

**The tax bug (found via item 5, "does this math pencil out?"):** effective tax rate was
`tax ÷ (assessed ÷ 0.10)` — a hardcoded 10% *residential* assessment level — in THREE divergent
copies (scorecard card, chat-sidebar card, and `main._resolve_market_value_and_tax` feeding the
**$25 report**). 4520 N Clark (class 517 commercial, 25% level) showed 2.06% when the truth is
~5.15% against ~$994K implied market (the report printed $2.48M — a 2.5× overstatement on every
commercial parcel, which also kept the report's >3.5% high-tax warning from ever firing).
**Fix:** `retrieval/property/assessment_level.py` (class prefix → ordinance level: 1/2/3→10%,
4→20%, 5→25%, incentive 6–9→10%, EX/RR→none); `PropertySummary` carries `assessment_level` /
`implied_market_value` / `effective_tax_rate` / `tax_year` computed ONCE server-side — no surface
recomputes. The ptaxsim bill year is labeled everywhere (the DB lags the calendar 1–2 years, so an
unlabeled bill next to the current AV silently mixed years). Gate: `test_assessment_level.py`.

**UX changes:** (1) **MiniChatDock** — grounded quick-chat bottom-right of the Scorecard; ALL
on-page asks (investigate chips via `InvestigateButton onAsk`, verdict next-step, header ask)
answer in place instead of navigating to the workspace; **ephemeral-unless-escalated** ("Continue
in the full analyst" carries the transcript via sessionStorage `ul_dock_handoff` → App.tsx seeds
the workspace). Supersedes the dashboard-model doc's sticky ask-bar concept. (2) accuracy
feedback → SVG thumbs in the **VerdictBand `footer` slot** (feedback sits with the claim, not the
page bottom). (3) SegmentPrompt → **post-sign-in global modal** (`useAuth` sets `ul_segment_due`
on OAuth return). (4) section grids `md:items-start` + regulatory top-6 constraint budget — kills
the stretch-gap dead space ("card = data source, height = data volume" inverted, per the
dashboard-model diagnosis; the full KPI-strip/identity-rail rebuild remains a separate decision).

**Reusable lessons:** Cook County market-value/eff-rate derivations MUST go through the class's
assessment level — a plausible-looking 2% residential-style rate on a commercial parcel is the
failure mode, and it read as correct for weeks. Derive interpretation fields server-side once;
two FE copies + one BE copy of the same formula is how they drift. `git stash`/`stash pop`
around a staged-but-uncommitted index silently unstages it — verify commit contents (`git show
--stat`) after any stash cycle.
