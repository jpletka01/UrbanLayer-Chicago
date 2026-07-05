# Growth instrumentation arc (2026-07-05) — SHIPPED (`main` @ `aa72fe4`)

Go-to-market layer on top of the shipped product (north-star Phase 1.5 → Phase 2). Four work packages,
live-verified against prod: **WP1 attribution + funnel events** (`visit_start` w/ referrer/UTM + persisted
first-touch; `scorecard_view`/`checkout_started`/`discovery_search`/`signup_completed`; money events
`purchase_completed`/`subscription_started` written **server-side by the Stripe webhook** with `visitor_id`
threaded through checkout metadata — EXCLUDED from the `/api/events` allowlist so they can't be spoofed);
**WP2 admin funnel** (`get_engagement_stats` gains a 6-step distinct-visitor funnel + channel classification;
FE funnel bars + channels chart); **WP3 SEO + privacy + Clarity** (meta/OG/Twitter/canonical in index.html,
`robots.txt` + `sitemap.xml`, `/privacy` English-only page + footer link, Microsoft Clarity gated on
`VITE_CLARITY_ID` — prod build-arg `xhsx626r62`, CSP updated both nginx lines); **WP4 capture** (segment
self-ID prompt, per-parcel 👍/👎 accuracy feedback, newsletter → `subscribers` table schema **v13**).
Strategy doc: `strategy/2026-07-05_growth-strategy.md` (the governing go-to-market operating guide).

**Infra set up same day (Cloudflare, free):** `jack@urbanlayerchicago.com` receives via **Email Routing**
(stale Namecheap `eforward` MX + SPF removed; Cloudflare route1/2/3 MX + `_spf.mx.cloudflare.net` SPF added)
and sends via **Gmail "Send mail as"** (smtp.gmail.com:587 TLS + 16-char app password — NOT the inbound MX
host Gmail auto-fills, and NOT the normal account password); `www` CNAME retargeted off the parking page +
a **301 www→apex redirect rule with "Preserve query string"** (verified: `?pin=` survives).

**Reusable lessons:** money/privileged analytics events must be **server-written only** (webhook), never in the
client allowlist, or the funnel is spoofable. Attribution must land **before** any channel work or spend —
otherwise every experiment is unmeasurable (the strategy's hard sequencing gate). A Namecheap domain's email
forwarding only works with Namecheap DNS; on Cloudflare you delete the `eforward` MX/SPF and use Email Routing.
Gmail "Send mail as" auto-fills the **inbound** MX server (`route*.mx.cloudflare.net`) — wrong; sending always
goes through `smtp.gmail.com` with an app password. A build-time `VITE_*` flag needs the ARG+ENV in the
Dockerfile **and** the build-arg in `docker-compose.prod.yml` (mirrors the committed-artifact three-line rule).
Current behavior documented in `frontend/CLAUDE.md` (tracking.ts / PrivacyPage / capture components) +
`backend/CLAUDE.md` (db v13 / `/api/newsletter` / payments analytics). Historical marker.
