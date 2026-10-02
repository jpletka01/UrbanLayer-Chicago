---
name: live-site-sweep
description: Check the live UrbanLayer site (or a local build) for console errors, page errors, failed requests and horizontal overflow on every main route, desktop and phone. Use after any deploy that touches the frontend or API responses, before sharing the site, or when a user reports "something looks broken".
---

# Live-site sweep

```bash
cd frontend && npm run sweep:live                                   # production
cd frontend && SWEEP_BASE_URL=http://localhost:5173 npm run sweep:live   # local dev server
```

`frontend/e2e/live-sweep.mjs` loads each route in `ROUTES` at 1440×900 and on an iPhone 15 profile,
waits for the network to settle (longer for the Property Profile), and prints `clean` or the
issues per route. It exits 1 if anything is found. It needs a Playwright browser once:
`npx playwright install chromium`.

It was clean on production on 2026-09-28 (16/16).

## Reading the results

| Issue | Usually means |
|---|---|
| `console: …` | A real error in the page, or a CSP violation. The CSP lives in `frontend/nginx.prod.conf` (one `map $csp`); an inline script needs its sha256 there. |
| `401 /api/…` | An auth-only call made for an anonymous visitor. Gate it on the signed-in user (see `useAuth` / `can_refresh`). |
| `4xx/5xx /api/…` | A backend regression. Reproduce with `curl` against the same URL. |
| `pageerror: …` | Uncaught exception, e.g. hooks called conditionally (ESLint `rules-of-hooks` is an error for a reason). |
| `horizontal overflow Npx` | A layout bleed. `npm run test:mobile` names the element; fix with `overflow-x-clip` on the section root. |

## Related checks

- `npm run test:mobile` (with `E2E_BASE_URL=https://urbanlayerchicago.com` for prod) runs the
  deeper phone-layout audit: 8 routes × 5 devices, and it names the element that overflows.
- Lighthouse (performance/accessibility) isn't automated; mobile performance was 29–56 in
  September (single 4 MB bundle), a known next step.
- When adding a page, add it to `ROUTES` here and to `PAGES` in `e2e/mobile-overflow.spec.ts`.
