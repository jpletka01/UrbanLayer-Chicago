# /api/report 504 incident — reranker, not OOM (2026-06-16 → resolved 2026-06-18) — SHIPPED

The real cause of the report 504s was the **reranker hanging `semantic_search`** (>40–60s/search × 5 parallel in
`extract_zoning_standards`), NOT the OOM first suspected. Fix = take the reranker out of the report path via the
precomputed **zoning cache** (DEPLOYED & VERIFIED LIVE 2026-06-18, `main` @ `69d8481`) — see `guides/zoning-cache.md`.
Also shipped: subprocess-isolated PDF render (`backend/report_render.py`, ~118 MB), swap 2→8 GB, nginx
`/api/report` 180s, discovery-index interning, the zoning markdown-fence fix.

**Reusable lessons:** blackholing GIS locally *disproved* the first theory rather than assuming it — reproduce to
falsify. A generous dev Mac compresses memory (slow cascade) where the 8 GB prod box OOM-kills outright — the same
bug wears a different failure mode by environment. The reranker re-enable (bounded concurrency + 20-batch) was
profiled on prod, found still too slow (CPU-bound not swap), and **rolled back** — don't retry it. Active truths
live in `core/known-issues.md`; full story on the About page → **Feasibility Report / Zoning Cache**.
