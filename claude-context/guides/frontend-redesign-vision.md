# Front-end redesign — vision brief

Version 3.1 · 2026-11-07 · Owner: Jack · **Status: Phase 1 prototype built behind `?ui=next` (decision Items 76–78).**

**This brief and the decisions file govern the new UI (`frontend/src/ui-next/`).** The Bento Pro guides, `guides/page-design.md` and the older layout docs describe today's live UI; where they disagree with this brief, this brief wins for new work. **No satellite map anywhere in the new UI** (Item 78).

The reference for UrbanLayer's front-end rewrite: what it is for, how the pages fit together, and the
rules every page follows. Visual design and the build are checked against it. Labels: **Approved** =
decided; **Draft** = agreed in shape, details open; **Ruled out** = decided against.

The detailed design pages (private Claude artifacts, Jack's account) hold the wireframes this summarizes:
site map rethink, Property Profile blueprint, Profile tab designs, Discovery wireframe, and the FigJam
site-map board, plus the landing page, chat page, Deep analysis and subscription wireframes. Ask Jack
for links; they are not public.

Until the rewrite ships, `guides/page-design.md` still governs the live site. Where this brief disagrees
(for example color roles, the floating nav, the chat panel), it describes the *new* front end, not
changes to make to today's.

## Why we're redesigning

A builder who tried the site was "utterly confused" and said he wouldn't pay for a product whose value
he couldn't understand. His specific points:

- **Discovery was a hassle:** too many options before any result, an unbalanced split between search and
  map, annoying search mechanics, lots on the map that showed no information.
- **The Profile said little in many words:** too many maps and moving pieces, walls of text, no
  connection from one part to the next, a ~20-second first load.
- **The maps were ugly:** business names crowded the satellite view; the zoning colors looked bad. (Satellite is out of the new UI entirely, Item 78.)
- **Nothing said what mattered:** black, dark gray and a little orange everywhere, so primary and
  secondary looked the same.
- **Chat broke the flow:** asking replaced the page with no warning, and the answer failed with
  "Something went wrong".

## Who it's for — Approved

**Builders and small developers, not the people who will live there.** They want to know three things
about a lot: what the code lets them build, whether the City will let them, and what it would take.
Features earn a place by answering one of those (livability extras such as walk-time rings were dropped
for this reason; the walk score is enough).

They spend their time on the **Property Profile**. Discovery is how they find lots; the Profile is where
they decide.

## Rules for every page — Approved

1. **The answer comes first.** Every page and tab opens with one sentence that states the finding.
2. **Pictures before sentences.** A fact gets a sentence only when no tile, bar, chart, chip or map
   layer can carry it.
3. **One map per page,** with layers that turn On / Dim / Off. Streets drawn as empty space, no business
   labels, a designed zoning palette. Reference: the Cities: Skylines 2 OSM toolkit map
   (`research/15-ui-data-inspiration.md` §2.4, local only).
4. **Only data that holds up.** Show a figure only when it means the same thing for every property.
   Exempt taxes, $1 transfers, quit claims and lowball assessments are labeled for what they are and
   never feed an estimate. When records disagree, say so ("built 1928–31 · records differ").
5. **Say how much we know.** Every filter and figure shows its coverage; unknowns are drawn hatched,
   everywhere, and can be included or left out.
6. **Compare locally:** the census tract against its community area, never against the whole city.
7. **Asking never leaves the page.** The analyst opens beside what you're looking at.
8. **Every visible lot opens something,** even "not in our data yet".
9. **Color has jobs:** one for "this property", one for "you can click this", one for "this costs
   money", status colors used sparingly. Chosen 2026-11-07 (Item 74): SnowUI's colors for the frame,
   black for this property, the Coastal palette for charts.
10. **Fixed slots keep it simple.** New data takes an existing slot or goes in a collapsed details
    table; it never adds a new kind of card. Today's word budgets carry over.
11. **No financial advice.** Report facts and what the code allows; never project returns or say
    "you can build this".

## The app frame — Approved

- One **side panel on the left** in the ChatGPT style (from a template): the logo, an icon for each page
  (Search, Discovery, Saved, Chat, with a small menu for past chats) and the account; no recent-lots or
  chat-history lists (Item 74). A collapse button inside the panel
  shrinks it to a strip of icons. The same panel opens from a menu button on the landing page.
- **Left is for getting around, right is for the analyst.** Never two panels on the same side.
- Signed-in return visitors land on an in-app home (search, recent lots, saved lots that changed, recent
  chats) instead of the marketing page.

## Property Profile — Overview approved, tabs Draft

A tabbed dashboard: the first tab answers, the others prove it.

**Overview**
- The top band is the page's **one map**, opening on the quiet street base (no satellite) with the lot outlined and the address
  over it. A street photo opens full size from it (a 4:3 photo can't fill a wide band).
- A full-width tab bar: Overview · Build · Money · Neighborhood · History · Deep analysis, with Ask,
  Sources and Export PDF as icons on the right. Once you scroll, the header shrinks to one slim bar: a
  short address, the current tab as a menu, and the same three icons. Every Profile tab works this way.
- The answer in one sentence ("Zoned for up to 6 units; 2 are built").
- **One tile per tab** with its key figure, a small visual and at most one warning. No separate "what to
  check" box. Tiles reflow from three to six; a seventh tab means two should merge.

**Every tab has the same shape:** takeaway sentence → one wide main visual → two or three smaller
visuals → collapsed details table. Missing data keeps its slot ("None on record").

| Tab | Answers | Main pieces |
|---|---|---|
| Build | What can I build here? | Allowed vs built for floor area, units and height (the binding limit highlighted; a "compare with another district" ghost bar replaces the What-if card); the lot in 3D on its real block (today's building, the largest allowed around it, neighbors' heights; replaces the 2D side view); pending zoning changes as a stage tracker with before/after numbers; rules as yes/no chips |
| Money | What would it cost or earn? | Taxes (exempt case: "at a typical rate"); the assessor's estimate, flagged when far below sales; comparable market sales on a wide map with the "nearby" rule printed as chips; rent for this building's unit sizes; incentives; value and taxes over time |
| Neighborhood | What's the area like? | Walk/transit/bike scores; construction nearby on its own map, clickable for what's being built; crime as violent vs property, per resident; top 311 concerns; "who lives here" as small charts vs the community area; schools |
| History | What has happened to this property? | One filtered timeline of market sales, transfers, permits, violations and rezonings; building facts with "records differ" ranges; no predictions |

**Check a project — part of Deep analysis.** A builder picks or adjusts a project and gets a path, never
a yes: fits the zoning numbers we checked / needs a variation / needs a rezoning /
needs a planned development / use not allowed. One row per limit, the deciding one highlighted, who
decides (the alderman, from the ward data already stored), precedent nearby, and what wasn't checked.

## Deep analysis — Draft

The paid layer: a sixth Profile tab that is a **feasibility study of one project on one lot**, read in
the order a builder decides. It is not a second Profile (the free tabs are organized by topic, this tab
by the decision) and it maps one-to-one to the PDF export, which is today's report generator.

- **Start from a project:** ready-made starting points for the lot (largest allowed, a 3-flat,
  townhouses, your own), each marked fits or not, adjusted with plus and minus buttons. No blank form.
- **The lot's real outline in 3D** (County parcel geometry; the report already classifies front, side
  and rear edges), rotatable, with the allowed building around the project and anything over a limit in
  red, beside the verdict and five limit marks. Odd lots get "approximate"; a missing outline shows
  dimensions only, never an invented rectangle.
- **For and against this project,** with icons. Every figure opens its meaning and actions (the TIF
  card links out to the City; upzonings use a ¼-mile radius and show on the page's map).
- **Getting it approved:** one numbered path (talk to the ward office, gather documents, file the
  amendment, Council vote, permit, inspections). The current step is highlighted with its one or two
  actions; City links sit on the step that uses them; Done moves the highlight on. An application kit
  prefills the facts we know and drafts a note to the ward office; the builder sends everything.
- **Rules that affect the project** as a row of tiles, problems first; checks that don't apply fold into
  one tile. **Uses** as four icon tiles that open into the full list with approvals and code sections.
- **Your numbers:** sliders for rent, price, build cost, taxes and a target return, starting from the
  lot's data, with the area range and the new-construction range drawn as colored bands on each slider.
  The result is arithmetic against the builder's own target, labeled as their assumptions. This is a
  deliberate, user-driven exception to "no pro forma": we never judge the deal.
- **Before you buy:** a short checklist whose items link back into UrbanLayer.

## Pricing — Approved

- **A subscription, not a price per lot.** Paying per address made builders bet on a lot before seeing
  its value. **Pro: $19 a month or $199 a year** (saves $29, about 1½ months free; show it in dollars).
  No lifetime plan.
- **The free version is never punished.** No blurred or locked sections; the free tabs are complete; a
  fully open example lot and one free Deep analysis show the value before paying.
- **Chat limits from cost.** About 3.6¢ a question on development traffic (Sonnet 4.6 at list prices;
  re-measure about a month after real users arrive). Signed-out visitors get 3 questions in total, then
  sign in. Free accounts and Pro get monthly allowances (about 50 and 300, to confirm), with an overall
  spend cap. Past the limit, users can connect their own Claude or ChatGPT (an MCP connector) with an
  opt-in handoff of the current conversation.
- **Sign-in only through Google, Apple or Microsoft,** never email, so limits can't be reset with
  throwaway addresses.

## Discovery — Approved

- **Opens on the map of the city (Explore mode):** every lot drawn as its shape, colored by one measure
  you pick; quick filters dim rather than hide; "Search these lots" turns a view into a search.
- **One search box** for an address, neighborhood or description; suggestions are autocomplete. A
  description becomes editable chips via the existing rule-based parser
  (`backend/discovery/compile_text.py`, deliberately not an LLM); unknown words show as
  "not understood".
- **Six goals as "Try" chips:** vacant land near transit, teardown candidates, room to add units,
  underused commercial in a TIF, coach house candidates, recent sales.
- **One focus at a time:** List (picture cards) or Map (matches only, "N lots in view · List them"; no
  card strip). Cards: photo, address, zoning, lot size, room to build, last market sale, at most one
  *serious* warning (demolition order, vacant-building case, pending rezoning, landmark), bookmark.
- **Filters sheet with only filters that have data,** each showing coverage, presets plus a custom
  value, an include-unknowns choice, and a live "Show N lots" count. Unknowns get their own hatched
  histogram bar.
- **Transit is one control:** close to any of L, Metra, bus or Divvy within a 5/10/15-minute walk; extra
  rows must all be true; plus a "transit-oriented area" switch (the City's TOD rules).
- An address offers its Profile, or a search within a resizable ring. ZIP codes need boundaries first.

## Chat — Approved

- **On the Profile, a drawer** over about a third of the screen: on demand from the Ask icon, keeps the
  conversation across tabs, knows the lot, project and calculator numbers. "Open in full chat" opens a
  new tab, never replacing the page.
- **The full chat page:** the side panel with its history, and the conversation at reading width. A
  nearly empty first screen with one example question typing itself; a message box with an upload
  paperclip, dictation and an arrow to send.
- **Answers lead with text**, with small previews (lot, map, sources, chart) on standby. An opened
  preview fills the space above the message box; a minimize icon puts it back. The same on phones.
- **Sources** as a short list, one open at a time, each shown as what it is: a code quote, a code table
  trimmed to the columns used, data records as rows, or a single figure.
- **Memory across a conversation:** lots are kept by parcel number and the records each answer used are
  indexed, inside a sliding window with a summary, so switching back to a lot or asking about one record
  is exact. Today only the text of up to 20 earlier messages is sent back, and a conversation is capped
  at 10 questions.
- **Neighborhood questions:** words in chat with at most two previews (one map, one chart); the full
  data lives on the Neighborhood tab.
- **At the limit:** a frosted sign-in card (a bottom sheet on phones), which also offers connecting the
  user's own Claude or ChatGPT.

## Maps — Approved: the Cities: Skylines style is required (Item 80)

One map design for every page, so the Profile, Discovery, chat and Deep analysis read the same way.

**The look is the Cities: Skylines 2 OSM toolkit map, and the rewrite is not complete without it** (owner,
2026-11-07, repeated; Item 80). That means: a dimmed, desaturated base that nearly disappears; our own shapes
(parcels, buildings, zoning) each filled and thinly outlined in a color that means something; roads drawn by us
in a few classes with set widths and colors, on top, so streets read as clean gaps between blocks; no satellite,
no business labels. Mapbox's stock street styles cannot produce this; changing technology (for example MapLibre,
our own vector tiles, a custom style) is allowed if that is what it takes. No route flips to the new UI by default
until its map meets this look. How it was made: `research/15-ui-data-inspiration.md` §2.4.

- **A quiet base:** muted land, streets as empty gaps between blocks, street names only when zoomed in,
  no business or point-of-interest labels. **No satellite imagery** (Item 78): imagery competes with the lot and
  the data. Today's live Profile still opens on `satellite-streets-v12`, which
  prints business names; hiding the base style's POI label layers in `lib/useMapboxOverlay.ts` (the one
  place every map is created) is the quick win, shipping with the live-site fixes.
- **Streets stay visible above zoning** (streets drawn over the zoning fill or a road mask; zoning is never clipped to blocks, which would draw a cleaner but wrong map: Item 75, M3); district codes are the only zoning labels.
- **The lot always on top** as a strong outline in the "this property" color.
- **One shared layer catalog** (base; the lot and buildings; zoning and pending rezonings; built vs
  allowed; rules such as TIF, transit area, landmark, planned development and flood; market sales and new
  construction; crime and 311; L, Metra, bus and Divvy). Every layer switches **On / Dim / Off**; pages
  differ only in which layers start on.
- **A key that builds itself** from the layers that are on, with counts in view and each source's date;
  it folds to one button. On phones, Key and Layers are two buttons that open half-height sheets.
- **Zoning colors by rule:** one hue per zoning family, darker as density rises; planned developments as
  an outline only. Exact colors come with the site palette, checked for color-blind safety in both themes.
- **3D is a mode of the same map** (a 2D/3D button on every map, Build opens in 3D, phones only in the expanded
  map; turn, tilt and reset): today's building on the lot in the lot's color, an illustrative zoning mass on Build
  (never "the largest allowed"), and neighbors at their measured height from the County's 2022 LiDAR, tinted by
  their zoning (Items 105-106; built, approved 2026-11-11).
- **One map instance per page,** reused across tabs and layers, which also ends the "WebGL context was
  lost" error.
- **Defaults:** Overview quiet street base + this lot; Build zoning, pending rezonings, 3D; Money market sales
  within ¼ mile; Neighborhood new construction within ½ mile; Discovery lots colored by the chosen
  measure; a chat answer shows only the layer it is about.

## Saved — Draft

In the rail: saved lots, searches and conversations. Named lists with a private note per lot; each saved
lot shows what changed since it was saved (sale, permit, rezoning introduced, new violation); compare two
or three; saves work before sign-in and move to the account after.

## Ruled out

| Idea | Why not |
|---|---|
| "Does it pencil" / pro forma | Financial advice we can't fully back up; credibility and legal risk |
| Where the tax bill goes | People want the total, not the split |
| Comparisons to the whole city | Too large to say anything about one block |
| Walk-time rings | Builders get enough from the walk score |
| Year built as a filter or sort | Known for about half the city, and records disagree |
| Filters with no data (units, open violations and ten more) | Hidden until the index has them |
| Minor violations on result cards | A fire-escape inspection isn't a reason to skip a lot |
| A permanent chat or sources side panel | Crowds the page and never goes away |
| The earth-tone infographic palette for the site | Reads as fall-themed; colors are chosen fresh in the visual phase |
| Paying per lot ($25 a report or an unlock) | Makes builders bet on an address before seeing its value |
| A lifetime plan | Running costs continue for every user, and the site's future is open |
| Blurred or locked sections in free tabs | Punishes free users; better they stay than leave |
| A floating Ask button | Bulky on phones; Ask sits with Sources and Export |

## Data work the designs need

Back-end work that can run during the visual phase.

| Work | Unblocks |
|---|---|
| Split the Profile request by tab | Overview in a few seconds instead of ~20; other tabs load behind it |
| Fill the Discovery index: lot size for every lot, units, open violations (the City's citywide dataset), 311, crime, floodplain, brownfield, Opportunity Zone, coach-house area, ARO zone, overlays, SBIF/NOF areas, ward | Roughly twice as many working filters; most are point-in-area checks the Profile already runs per lot |
| Metra stations, bus lines, Divvy docks in the index | The single transit control |
| Building type from the assessor's class code (100% of lots) | Replaces the incomplete `land_use` enum |
| 311 counts within ⅛ mile or the tract, against a baseline (`three11.py` groups by community area only today) | Flagging unusual noise, rodents or flooding near a lot |
| Census B25024 (homes by building type) | "What's built around here" |
| Rezoning history near a lot; the alderman's rezoning record | "Who decides" and precedent |
| Permit processing times by area; sales and rents of new construction | How long it takes; what the finished product is worth nearby |
| Photos: Street View on the Profile, aerial crops on cards | Street View: 10,000 free images a month, then about $7 per 1,000 (Google, post-March-2025 pricing; confirm before relying on it). Check cost at real traffic before cards use it; images can't be stored |
| ZIP code boundaries (Census ZCTA) | Searching by ZIP |

**Discovery index coverage, measured** on the 2026-10-29 citywide index copy (882,328 lots; production
may be slightly newer): class, L-stop distance, vacant, TIF, Enterprise Zone, assessed value 100%;
zoning group 99.6%; improvement ratio 94%; `land_use_class` 93.9% (mixed_use, institutional and exempt
never appear); density band 86.5%; last sale / sale recency 67.8%; land sqft 66.8%; year built and bldg
sqft 50.7%; teardown 50.3%; upside 49.4%; price per sqft 34%; value percentile 4.4%; and 0% for units,
open violations, 311, crime, floodplain, brownfield, Opportunity Zone, ADU area, ARO, overlay, SBIF/NOF
and ward.

Also needed for Pro and chat: Stripe subscriptions ($19 / $199), monthly chat allowances and the
3-question signed-out cap; later, the MCP connector for users' own AI.

## Fixes that can't wait for the redesign

- **Chat fails with "Something went wrong while answering"** (reproduced). It is `_CHAT_ERROR` in
  `backend/main.py`, a server-side stage exception; the cause is in prod `request_logs.error_message`.
  Anonymous chat is allowed, so it is not a sign-in issue.
- **Asking from the Profile or Discovery replaces the page** with chat, with no warning
  (`MiniChatDock` escalate and Discovery's `onAskArea` both `navigate()` in place).
- **The ~20-second first Profile load.**
- **Lots on the Discovery map that open nothing.**
- **"WebGL context was lost"** on pages with several maps.

## Open questions

Parked on purpose; none blocks the visual design. Each must be answered before its feature is built.

| Question | Answer before |
|---|---|
| Tabs on a phone: scrolling tab strip, or one page with jump links? | Detailed Profile mockups |
| Exact chat allowances; whether past report buyers and voucher holders convert to Pro time; a short trial | Turning purchases on |
| Race and ethnicity: details only, or left out (fair-housing steering concern)? Schools: include, and which measures? | Building the Neighborhood tab |
| Renderings of new buildings: link out to filings, or skip? | Building the construction map |
| Check a project: vague projects, low-confidence lots, two lots combined | Building Check a project |
| Which violation categories count as serious enough for a card? | Indexing violations |
| Which missing data to add first? | Starting the data work |
| Alerts for new matches on saved searches: early or later? | Building Saved |
| Which five quick filters; are the goal names right? | Detailed Discovery mockups |

## What comes next

1. **Structure is done (2026-11-07).** Every page is wireframed: site map, Profile (Overview approved,
   tabs drafted), Deep analysis (draft 7), Discovery (approved), landing (approved), chat (approved),
   the subscription flow and the shared map design. Sign-in, Settings and About are restyles.
   Templates and the implementation plan followed the same day (steps 2 and 3).
2. **Visual phase:** the template is chosen (2026-11-07): **SnowUI** is the visual base, with a bottom-sheet
   library, a collapsible sidebar and a light/dark sidebar filling single jobs, and Lucide kept for icons
   (`decisions/2026-11_frontend-rewrite.md` Item 73; the files are CC BY 4.0, so the About page credits them).
   The visual system is chosen too (Item 74): SnowUI's frame colors and type, the Coastal chart palette,
   black for this lot. Zoning colors stay provisional until the map mockups.
3. **The build plan is approved (2026-11-07, Item 75).** The prototype is built in code behind a preview
   switch (the frame, Profile Overview and Build, the Ask drawer, one Discovery flow on today's data),
   checked against SnowUI, then tested with two or three builders on a real task ("Could you build a
   6-flat at this address?") against pass criteria written in advance. The map, data, chat, landing and
   commercial work follow in gated phases; every merge to `main` deploys and needs the owner's approval.
4. **Phase 1 prototype built (2026-11-07, Item 76):** behind `?ui=next` on today's URLs: the frame, Profile
   Overview (one tile per tab: units allowed vs built, property tax, walk score, last market sale; Item 77) and Build on today's
   `/api/scorecard`, the parcel map in the new look, the Ask drawer on the existing chat path, one Discovery
   flow. **Approved by the owner 2026-11-07** (Item 79; the map's look waits for the map tracks, Item 80).
5. **Phase 2 done (Items 81–83):** a first screen in about 2.5 s on production (Item 87). **The builder test is deferred**
   (no builders lined up, Items 88 and 111): it now runs at the end of the rewrite, before the old UI is deleted, not
   before each route switches. Next: the Profile response split (Phase 4).
6. **Phases 4–6 done** (the Profile in parts, the one map in the Cities: Skylines look, every Profile tab and
   Discovery; Items 89–104). **Phase 7 (data tracks) in progress:** LiDAR heights measured (Item 105), M6 3D done
   (Item 106); next M4 capacity, then M5 land in use. The runbook keeps the live status.
7. **Phase 8 done (2026-11-12, Items 113–117):** the full chat page, the landing and the signed-in home. Next:
   Phase 9, the commercial epics (quotas, billing and entitlements, identity, Saved), each with its own plan.

Update this brief when a decision changes; the design pages hold the detail.
