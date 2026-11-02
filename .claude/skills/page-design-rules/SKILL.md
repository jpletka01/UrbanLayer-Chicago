---
name: page-design-rules
description: UrbanLayer's rules for what a page shows and how — one answer first, evidence behind a fixed set of Lucide tool icons, color by role, buttons vs status labels, and the page budgets that keep text from creeping back. Use before ANY change that adds or edits text, a card, a figure, a caveat, a date, a link, a button or a color on the Property Profile or Discovery (and other app pages), and when reviewing such a change.
---

# Page design rules

The Profile once grew to ~3,000 words at equal weight because every PR added one correct sentence
("additive honesty"). These rules exist so that never happens again. They come from Jack's reviews
(2026-10-31, 2026-11-02), `plans/reports/Fixing an overgrown data page.md`, and decision Items 49-54 in
`claude-context/decisions/2026-10_build-queue.md`. Reasons, measured effect and the file map:
`claude-context/guides/page-design.md`.

## 1. What a block shows

A card, row or panel prints **only**:
- a **human headline** that states the finding ("Minimum lot area per unit", "10 N State St"), never an
  ID (no Clerk record numbers, PINs or section numbers as headlines);
- its **1–3 key figures**;
- its **status labels** (section 4).

Everything else is **evidence** and sits **one click away behind a tool icon** (section 3): dates, code
sections, record numbers, official titles, definitions, method notes, disclaimers, arithmetic, sources.
Do not print it, and do not add a sentence where a label or a tool would do.

Two levels only: the page, then one expand or one toggletip. Never a disclosure inside a disclosure
(dialogs such as the Sources sheet are fine).

## 2. Color = role, never hue

| Role | Means | Token |
|---|---|---|
| Neutral weight/size | importance | `text-*`, `dark-*` ramp |
| Orange | **clickable only**; at most ONE solid-orange element per viewport | `action` (solid), `link` (outline/text) |
| Violet | **costs money only** | `premium` |
| Amber | check / act on this; ≤ 3 on the first screen (shared by rows and labels) | `status-warning` |
| Red | a blocker | `status-danger` |
| Green / blue | genuine success / passive info, rare | `status-success` / `status-info` |

A verdict category is **neutral**, never amber. Raw palette classes (`text-amber-400`) fail
`components/scorecard/palette.test.ts`.

## 3. Tools: one Lucide icon per meaning, same order everywhere

Use `ToolTray` (`frontend/src/components/ui/ToolTray.tsx`); never hand-roll a tool or use a text glyph
or emoji as an icon. Icons come from **`lucide-react`** only.

| Order | Tool | Lucide | Holds |
|---|---|---|---|
| 1 | Dates | `Calendar` | every date for the item, each with its plain meaning (`DateLine`: "City Council last acted", "We read the ordinance text", "Checked") |
| 2 | Code | `Scale` | the Municipal Code section(s); opens the code text where we have it |
| 3 | Official record | `SquareArrowOutUpRight` | link to the Clerk / Assessor / City record (record number + official title in its tooltip) |
| 4 | Explain | `Info` | what it means / method / disclaimer, two sentences |
| 5 | Ask | `MessageCircleQuestion` | opens the analyst with a question about this item |
| — | More | `ChevronDown` | expands |

Tools are neutral gray and turn orange on hover/focus. Each is a real button or link with an accessible
name ("Dates: Minimum lot area per unit"). A year that changes the decision may stay visible beside the
calendar (`datesVisible`, e.g. the tax year). On a mouse, hovering previews a popover (moving into it keeps
it open) and a click pins it; on touch a tap opens it; Escape (focus returns), a second click or a click
outside closes it. Never hover-only.

**Links open in a new tab.** Every `<a href>` that opens a page gets `target="_blank" rel="noopener
noreferrer"` (`components/linksOpenNewTab.test.ts` enforces it). In-app navigation uses router links.

**Values carry their units.** Never print a bare number or a code word ("100", "not_allowed"): say what it
is ("parking can be cut by up to 100%", "coach houses not allowed").

## 4. Status labels vs buttons (shape grammar)

- **`StatusLabel`**: ≤ 22 px, 3 px radius, tint + Lucide icon, not focusable, no pointer. Information.
- **`Button`**: 8 px radius, 36–40 px, hover/focus/pointer. `primary` = solid orange (the one per
  viewport); `secondary` = orange outline + orange text (`border-link text-link`), never a dark outline
  on a dark surface.
- If a status needs an action, put a Button or tool beside the label, never inside it.

Confidence is a **visible state** via `ConfidenceState` (Lucide): Estimate `EqualApproximately`, Low
confidence (same icon, amber), Not checked `CircleDashed`, None found `CircleCheck`, Withheld
`CircleSlash` (value shows "—" + a reason ≤ 8 words), N/A `CircleMinus`. A verified figure has no label.
These states never move behind a tool (`guides/source-confidence.md`): only their *explanation* does.

## 5. The budgets (the page's owner)

`frontend/e2e/profile-budget.spec.ts` (in `npm run test:mobile`) holds the Profile's first screen and the
opened Build section to a baseline that only ratchets down (words with an 8-word allowance for live
state rows; amber ≤ 3 cap; one solid orange; page height). Raising a baseline is a hand edit with a
reason in the PR and a decision Item. Measure before/after with
`plans/2026-11-01_redesign-assets/firstscreen.cjs` (run from `frontend/`). Discovery has the same ratchet
(`frontend/e2e/discovery-budget.spec.ts`: the Start panel's and a recipe's results' first screen, desktop and
phone, and the dot preview's words; decision Item 57).

## Checklist for a change

1. Does the new text state a finding the user needs first? If not, it goes behind a tool.
2. Is any date, ID, section, definition or link printed? Move it into `ToolTray`.
3. Does every color have its role (section 2)? One solid orange per viewport?
4. Are buttons `Button`/orange-outline and labels `StatusLabel`?
5. Did the confidence state stay visible?
6. Run vitest, `npm run lint` (exit status: the warning cap), `npm run build`, `npm run test:mobile`
   (overflow + budget). Record the decision.
