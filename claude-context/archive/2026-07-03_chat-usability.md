# Chat usability arc — mobile + i18n (2026-07-03) — SHIPPED (`main` @ `7f128f0`)

7 phases + 2 bonus bug fixes, served-bundle-verified. Nav declutter under **icons-in-chrome / words-in-menus**
(Export/Share → `ConversationMenu` ⋯ kebab; 20-char nav-string CI budget); mobile map (ONE Layers popover,
count-labeled cluster dots, 14px touch picks, bottom-docked detail, peek summary strip); **per-message context
chips** (`ContextChipStrip` via MessageBubble `footer` slot); Tier-2 grounding (traffic graft, notable-only starter
chips); comfortable mobile density; message-limit counter.

**Reusable lessons:** ⚠️ **deck.gl aggregation layers do NOT render in interleaved `MapboxOverlay` mode** — hand-roll
clustering (verified empirically; don't retry HeatmapLayer). Icons in chrome, words in menus (vertical menus are
i18n-proof — es strings overflow bars). The **splash-swallows-streaming-answer race** (active-flag dip +
AnimatePresence `mode="wait"`) was bisected against main before fixing. Pipe `curl | grep` for served-bundle checks
(`echo $JS` gives false negatives). Current mobile/chat behavior is documented in `frontend/CLAUDE.md`. Historical marker.
