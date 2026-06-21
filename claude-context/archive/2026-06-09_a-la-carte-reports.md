# A La Carte Report Purchases ($25 One-Time)

**Completed**: 2026-06-09
**Status**: Shipped & live in production (the $25 report wedge is the core monetization; schema v9 is part of the current prod v11 DB).

## What Was Built
Added Stripe one-time payment flow so free users can buy individual PDF feasibility reports for $25 without subscribing to Pro ($99/mo). The purchase grants permanent re-download access for that specific address. This is the "wedge" from the North Star strategy — the first thing someone pays for.

## Implementation Details

### Database (schema v9)
New `report_purchases` table: `user_id`, `stripe_session_id`, `stripe_payment_intent`, `address`, `lat`, `lon`, `amount_cents`, `status` (pending/completed/refunded), `created_at`, `completed_at`. Location matching uses `ROUND(lat, 4) = ROUND(?, 4)` (~11m precision). Helper functions: `save_report_purchase`, `complete_report_purchase` (idempotent), `has_purchased_report`, `get_user_report_purchases`.

### Backend
- `payments.py`: New `create_report_checkout_session()` uses `mode='payment'` with Stripe. Refactored `_handle_checkout_completed` to dispatch on `session["mode"]` — `payment` → report purchase, `subscription` → existing Pro upgrade.
- `main.py`: New `POST /api/checkout/report` (creates one-time Stripe session), new `GET /api/report/access` (checks if user can download). Modified `/api/report` from `require_tier("premium")` to `require_auth` + inline access check (Pro OR purchased).
- `config.py`: Added `stripe_price_id_report` setting.

### Frontend
- `ReportPurchasePrompt.tsx`: New modal with dual CTA — "Buy Report — $25" (primary, one-time) and "Upgrade — $99/month" (secondary, subscription).
- `ScorecardPage.tsx`: Download button shows "Download Report — $25" for unpurchased (with highlighted styling), "Download PDF" for Pro/purchased. Checks `GET /api/report/access` after scorecard loads. Handles `?report_purchased=1` post-Stripe-redirect with auto-download.
- `PricingPage.tsx`: Added a la carte callout below pricing grid.
- `api.ts`: Added `createReportCheckoutSession()` and `checkReportAccess()`.

### Stripe Configuration
- Product: `prod_UfbN9xM7Tnwgm3` ("Site Report")
- Price: `price_1TgGAj0Bee22rkcDF1tThTSD` ($25.00 USD, one-time)
- Env var: `STRIPE_PRICE_ID_REPORT` in `.env`

## Key Decisions
- **Reports never expire** — once purchased, always re-downloadable for that address.
- **On-demand generation** — purchase grants the right to generate, not a cached PDF. User always gets fresh data.
- **Lat/lon matching (not address string)** — avoids normalization bugs with address formatting variations.
- **Webhook dispatch on mode** — `checkout.session.completed` now checks `session["mode"]` to distinguish subscription vs. one-time payment, keeping the single webhook endpoint.
- **Free users see both options** — the modal offers "$25 single report" as primary and "$99/mo unlimited" as secondary, letting users self-select.

## Files Changed
- `backend/config.py` — added `stripe_price_id_report`
- `backend/db.py` — schema v9, `report_purchases` table, 4 helper functions
- `backend/payments.py` — `create_report_checkout_session()`, webhook dispatch refactor
- `backend/main.py` — `/api/checkout/report`, `/api/report/access`, modified `/api/report` access logic
- `frontend/src/lib/api.ts` — `createReportCheckoutSession()`, `checkReportAccess()`
- `frontend/src/components/ReportPurchasePrompt.tsx` — new component
- `frontend/src/components/ScorecardPage.tsx` — modified download flow
- `frontend/src/components/PricingPage.tsx` — a la carte mention
- `.env` — added `STRIPE_PRICE_ID_REPORT`
