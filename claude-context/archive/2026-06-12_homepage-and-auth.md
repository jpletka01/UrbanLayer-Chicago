# Coherence audit step 3 — homepage + auth (2026-06-12) — SHIPPED

Address-first hero (`AddressInput`/`HeroEntrance` → `/scorecard?address=`, librarian chat secondary); anonymous
chat opened (gate removed, 3/day IP limit, in-memory only, 429 UX); conversation endpoints `require_auth` + PATCH
ownership check; anon CSRF-cookie bootstrap on `/api/auth/me`; persona intent-routing. Step 3 of the coherence
audit (superseded in part by step 4, `strategy/2026-06-15_homepage-coherence-pass.md`). Auth mechanics are the
About page → **Authentication & Security**. Historical marker only.
