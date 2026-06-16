# Homepage Coherence Pass + In-Session New Chat (2026-06-15)

**Status: IMPLEMENTED IN WORKING TREE — NOT committed, NOT pushed, NOT shipped.**
On branch `main`, 14 files modified (unstaged). `tsc --noEmit` clean, 51/51 vitest pass,
en/es locale parity verified, production build succeeds. **Push to `main` = deploy**, so this
needs Jack's explicit approval before it goes live (per CLAUDE.md workflow rules). Until then,
treat every "fixed/resolved" claim below as *in the working tree*, not live on prod.

This is **Step 4** of the product coherence audit (`product-coherence-audit.md`), continuing the
homepage/entry/funnel work after Steps 1–3 (shipped 2026-06-11/12). It was produced through a long
analysis-first thread; this doc preserves both the **decisions** and the **reasoning frameworks**,
because the frameworks are the reusable part.

---

## 0. One-line summary

Took chat fully off the homepage (address-only hero), reconciled the homepage→Scorecard transition
(naming + a state-dependent search box that kills the duplicate-search moment), trimmed the top nav
to the parcel spine, canonicalized the product's vocabulary, and gave the in-workspace "New Chat" a
proper reset-in-place behavior with a ready empty state. Several adjacent items were **deliberately
deferred or judged acceptable** — see §4.

---

## 1. Decisions implemented (the A–F spec + New Chat)

Lettering matches the implementation spec used in the session.

### F — Naming canonicalization (vocabulary)
- **Free assessment surface = "Scorecard". Paid artifact = "Development Feasibility Report" (unchanged).
  Chat = "analyst".** Retired the competing nouns: `file`/`dossier` (marketing-only metaphor that was
  itself the source of sprawl) and `librarian`/`Analyst`.
- ES canonical term for the Scorecard = **"Ficha"** (matches nav + pricing + depth card).
- Hero subline now **names its destination**: "…all in one free **Scorecard**" (the INCLUDE option Jack
  chose). This also closes the first-critique gap where a user typed an address with no idea they'd get
  something called a "Scorecard."
- Surfaces changed: `landing.json` (heroSubline, howItWorks steps, depth card), en+es. The deleted hero
  chat strings' content was later **reused** for the New-Chat empty state (good content, wrong place).

### B — ScorecardPage two-shell model + failure-recovery handoff
- **One boolean drives the layout:** `searchProminent = !loading && !data && errorShape !== "question"`.
  Prominent (big search) iff re-entering an address is the next action (empty / address-typo);
  demoted (compact bar) otherwise (loading / success / code-question redirect).
- **This resolves the *harming* part of the homepage→Scorecard seam** — the duplicate, pre-filled
  search box that re-posed the question on arrival ("did my search go through?"). On a resolved
  address the search demotes and the result leads.
- **Failure-recovery handoff:** `classifyFailedInput()` decides address-typo vs. code-question **once**
  when the error is set (stored in `errorShape`/`errorQuery`, not re-derived per render). Question-shaped
  → a **neutral (non-error-colored)** redirect card → `/?q=<text>` auto-send into the analyst.
  Address-shaped → existing error + format guidance + a quiet "ask the analyst" secondary.
- Reuses the existing `?q=` auto-send (same path Investigate buttons use) — no new chat plumbing.

### C — Architect persona card → functioning chat door
- Re-pointed `action:"chat"` from the (now-deleted) hero-prefill to `navigate('/?q=<question>')`.
- Added an explicit per-card action cue ("Ask the analyst →" / "See the Scorecard →") — the cards
  previously read as descriptive example text, not as clickable doors.

### A — Removed the hero chat affordance entirely
- `HeroEntrance` is **address-only**. Deleted the mode toggle, the in-hero ChatInput, the librarian
  link, and the `onChatSubmit`/`chatPrefill`/`startInChat` props. `App.tsx` lost `heroChatPrefill` and
  the `?analyst=1` wiring (`sendMessage` stays — `?q=` auto-send still uses it).

### D+E — Nav trim + footer
- Top nav (`PageHeader`) is now **Scorecard · (Discovery, conditional) · Pricing**.
  - **Analyst removed** — a top-nav slot is co-equal billing, which violates the "unequal in weight"
    discipline for chat; its destination was also broken (homepage in a toggled state).
  - **About unlinked** from the customer UI. The `/about` route stays in `main.tsx` (direct URL) — it's
    Jack's architecture/interview asset, not a customer surface; provenance for skeptics already lives
    in the homepage footer's Data Sources block.
  - Fixed `navItemsFor` so Discovery inserts after Scorecard (`[scorecard, discovery, pricing]`).
- Footer "How it works" link **retargeted** off `/about` to a same-page `#how-it-works` scroll
  (added the `id` to the HowItWorks section).

### New Chat (in-session) — reset-in-place
- Added a `composing` flag; `active = messages.length > 0 || streaming || composing` so the workspace
  can render with zero messages (a ready empty composer).
- `clearWorkspace()` shared teardown; **`reset()`** (exit-to-home: logo/delete/clear-all) sets
  `composing=false` + navigates to splash; **`handleNewChat()`** (in-place) sets `composing=true` +
  navigates to `/` (drops `/c/:oldId` so a refresh can't resurrect it). `sendMessage` clears `composing`
  at entry (so the flag never lingers into later message-clearing paths).
- Stream **abort was already wired** in `useChat.reset()` (AbortController); AbortError is swallowed, no
  error banner; clearing messages before `streaming` flips false means no partial turn is persisted.
- **Persistence is incremental** (`appendMessages` on each stream-complete), so completed turns are
  already saved — reset-in-place needs no extra save; only the in-flight (incomplete) turn is discarded,
  which is correct. Anon = in-memory only (unchanged).
- **Empty state (required, not optional):** centered icon + heading + subline + three example chips.
  Chips **fill the composer, no auto-send** (see §3 for why this differs from `/?q=`).

---

## 2. Reasoning frameworks worth preserving (the reusable IP)

These shaped every decision above and should govern future homepage/funnel/chat work.

- **Focused funnel, NOT a tool launcher.** The product deliberately subordinates everything to one
  front door (address → Scorecard) and surfaces other tools contextually. This is "clean" in the sense
  of *coherent/unconfusing*, and deliberately *not* clean in the sense of "every tool is one click from
  a cold start." That trade is intentional. Judge it against who actually arrives: right for
  "evaluate this parcel" intent, friction for "I want tool X directly" intent.

- **Chat: "distinct in kind, unequal in weight."** Chat is contextual/subordinate — never the front
  door, never a co-equal top-nav peer. Its proper homes: the analyst inside a file (Investigate), the
  failure-recovery handoff, and (in-session) the New-Chat empty state. The funnel's own logic excludes
  chat from the homepage: interrogation presupposes an open file, so the analyst-in-file role is
  *premature* at homepage time; only the parcel-less "librarian" is even a candidate, and the handoff +
  persona card already capture that intent — making a hero chat box redundant.

- **Distinct-modes over a smart omnibox.** When resolving the old address/chat ambiguity, we chose
  explicit address-first entry with **intent inference demoted to a failure-recovery net** (a non-address
  input fails, *then* offers chat) rather than an omnibox that co-equally accepts questions and addresses
  and guesses. The omnibox would re-muddy the front-door identity and replace a legible label-error with
  an illegible inference-error.

- **Inconsistency triage: design vs. user-visible vs. user-harming.** Not every inconsistency is a
  problem. The homepage→Scorecard **header/visual swap** is a *design* inconsistency that rides the
  near-universal "marketing page → app" schema (lobby → building); it is barely user-visible (chrome
  blindness, goal-focused attention) and **non-harming** — so we deliberately did **not** unify the two
  visual systems. The *harming* part was the duplicate search box (foveal, re-posed the question), and
  that is what Section B fixes.

- **Auto-send vs. fill-no-send.** `/?q=` handoff + persona cards auto-send because the user already
  *committed* to a specific question (typed it, or clicked a labeled scenario). Empty-state chips
  fill-without-send because they're starter examples meant to be edited before sending. Intentionally
  different, not an inconsistency.

---

## 3. Verification

- `npx tsc --noEmit` → exit 0.
- `npx vitest run` → 51/51 pass (incl. `PageHeader.nav.test.ts` — Discovery still inserts at
  scorecard+1; order is `[scorecard, discovery, pricing]`).
- All four edited locale files parse; new keys at full en/es parity.
- `npm run build` → succeeds (the >500 kB chunk warning is pre-existing, unrelated).

---

## 4. Deferred / judged-acceptable / NOT done (read before assuming "coherence is solved")

1. **Cold-start direct-to-chat for a returning power user — DEFERRED.** A user who lands cold on the
   homepage wanting a *fresh, parcel-less* chat has no first-class door (their paths are the address-box
   redirect or the persona card). Deferred until Phase 2 validation shows the chat/librarian power user
   is a real, converting segment. The fix, *if* validated: a dedicated `/research` (or `/analyst`)
   destination with its own empty composer + a "New chat" that lands there — which is the point a
   repointed top-nav item would finally be justified. Do **not** pre-build this for an unvalidated audience.

2. **Visual/header unification of homepage ↔ inner pages — NOT done, by judgment.** The cinematic-hero →
   utilitarian-Scorecard aesthetic shift and the appearance of `PageHeader` remain. We judged this
   non-harming (rides the marketing→app schema). Revisit only if the goal becomes a seamless single
   visual language rather than the conventional marketing/app split.

3. **Price/Pricing on the homepage — UNTOUCHED.** Pricing is still footer-only on the homepage (no
   above-the-fold mention, no persistent homepage nav). This is the original first-critique finding #1
   and is the most actionable still-open item that doesn't depend on validation data. Suggested as the
   next thing to scope if Jack wants to keep going.

4. **Trade explicitly accepted:** removing the hero chat link (A) also removed the homepage's one
   mention of code research, so the **differentiator** (cited municipal-code reasoning) is now surfaced
   only contextually (handoff, persona card, in-session empty state), not on the cold hero.

5. Older audit §10 items unchanged by this pass: Explorer/Discovery free-teaser depth, TOD radii map
   layer, paywall-modal i18n, unauthenticated upload GET, anon-friendly purchase.

---

## 5. Files touched (14, all frontend)

`App.tsx`, `components/ChatInterface.tsx`, `components/ScorecardPage.tsx`, `components/PageHeader.tsx`,
`components/landing/HeroEntrance.tsx`, `components/landing/PersonaScenarios.tsx`,
`components/landing/Footer.tsx`, `components/landing/HowItWorks.tsx`,
`locales/{en,es}/landing.json`, `locales/{en,es}/pages.json`, `locales/{en,es}/chat.json`.

When this ships, archive per `claude-context/README.md` rules and move the relevant status lines into
an `archive/` entry; until then it stays here as active, un-shipped work.
