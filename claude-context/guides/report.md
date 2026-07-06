# Feasibility Report (PDF) — Living Guide

The $25 **Development Feasibility Report** is the revenue wedge: a per-unit PDF a professional
hands to a client, lender, or partner. Current architecture (V6, shipped & live). Historical
plan/audit trail (V3→V6, R5–R7) is archived — see `archive/2026-06-report-saga.md`.

## Generation path

`GET /api/report` (`backend/main.py`) →

1. **Assemble** the same retrieval the Scorecard uses (property / regulatory / incentives / zoning /
   comps). No sales/assessment fetch is skipped here the way `development_feasibility` chat does.
2. **Zoning** comes from the precomputed **zoning cache** (`ingestion/data/zoning_cache.json`, read by
   `backend/zoning_cache.py`), **not** live semantic search — the reranker is out of the report path
   entirely. See `guides/zoning-cache.md`.
3. **Synthesize** deterministically — ~29 opportunity/constraint rules, not a free-form LLM essay, so
   the prose never contradicts the tables.
4. **Render** HTML/CSS → PDF via **WeasyPrint** over the Jinja template `backend/templates/zoning_report.html`,
   with matplotlib map overlays (zoning / construction / comps maps, auto-scaled distance bars).
5. **Localize** deterministically via `backend/report_i18n.py` (`MESSAGES` catalog; no LLM — English is +0ms).

## Render isolation (why it can't OOM the box)

WeasyPrint `write_pdf()` runs in an **isolated child process** (`backend/report_render.py`): the parent
spawns `python -m backend.report_render` with HTML in a temp file, PDF out. The child imports *only*
WeasyPrint (~118 MB peak) — not the FastAPI app or the ~3 GB discovery index — sets `oom_score_adj=1000`,
carries an `RLIMIT_AS` backstop, and is killed by a parent wall-clock timeout → a clean **503** instead of
an OOM-killed worker. Report generation is bounded by `Semaphore(2)`; `write_pdf` is offloaded off the event
loop. (Backstory: `guides/zoning-cache.md` + `archive/2026-06-16_report-oom-reranker.md`.)

## What the report contains

Page-1 **Development Snapshot** decision box (lot · zone · max buildable · value · key constraint · approval
path) · comp-implied valuation with honest data-limit handling · FAR-utilization framing ("existing X sf uses
Y% of the FAR-allowed Z sf") · indicative unit yield from authoritative minimum-lot-area tables · a
SIMPLE/MODERATE/COMPLEX **approval pathway** · an **Ownership Intelligence** read from sales/tax signals
(Cook County exposes no owner names) · zoning/construction/comps maps with reference rings.

## Honesty rules (deliberate refusals are part of the design)

- Land-value ranges render **only with ≥3 land-bearing comps** (condo-dense blocks rarely have them) —
  else a labeled **"Valuation Indicators"** fallback anchors on median comp *sale price*.
- Tax-exempt parcels get a **"Tax-Exempt (Class EX)"** callout, not a residential comp number.
- **No** automated pro-forma/IRR, **no** "PERMITTED" entitlement verdicts, **no** fabricated parcel geometry.

## Known limits / data-blocks

| Area | Status |
|------|--------|
| Parcel map geometry | Blocked on data — Cook County GIS intermittent. When geometry is unavailable, render the **dimensions grid only**; never fabricate a rectangle (mock override must not either). |
| `year_built` | Data gap for some PINs — CCAO characteristics (`x54s-btds`) 400s on some queries; nonconformity analysis silently no-ops when null. |
| Ownership | Confirmed hard limitation — no open bulk source for owner names (Recorder has no public API; ATTOM/CoreLogic are paid). |
| Setbacks / min-lot | AI-supplied values in the zoning cache are not cross-validated against an authoritative source; **parking deferred**. |

## Verification parcels (report QA)

- **EX subject** `14283190070000` (481 W Deming Pl — *not* 443 W Wrightwood, a different parcel) — tax-exempt path.
- **Taxable control** `14331030110000` (642 W Belden) — normal valuation path.

## Key files

`backend/main.py` (endpoint) · `backend/report_render.py` (subprocess isolation) ·
`backend/templates/zoning_report.html` (Jinja/CSS) · `backend/zoning_cache.py` (+ `zoning_cache_build.py`) ·
`backend/report_i18n.py` (localization) · `backend/config.py` (map radii: comps 0.25mi, construction 0.5mi).
Frontend entry: `fetchReport()` / `createReportCheckoutSession()` / `checkReportAccess()` in `src/lib/api.ts`
(all take a `SelectedParcel`; PIN-keyed when a pin exists).
