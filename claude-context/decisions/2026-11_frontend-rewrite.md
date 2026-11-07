# Front-end rewrite: engineering decisions

The rewrite of the front end described in `guides/frontend-redesign-vision.md` (the vision brief). Format: see `README.md` in this folder. The wireframes and the visual-system draft are private design pages in the owner's account; the decisions below restate what a reader of the code needs.

---

## Item 73: SnowUI is the visual base; three other kits fill single jobs (2026-11-07)

**Decision: the new front end takes its look from the SnowUI dashboard kit ("Dashboard UI Kit - Dashboard, Free Admin Dashboard", by ByeWind, Figma Community, CC BY 4.0).** It sets the visual language: quiet neutral surfaces separated by fill rather than borders or shadows, 16px card radius, tiles with one key figure, wide chart blocks, and one highlighted bar among gray ones. It is a reference for the look, not a component library: SnowUI ships Figma drawings, and the components are built in this repo's React + Tailwind stack. Three other files each fill one job:

| Job | File (Figma Community, all CC BY 4.0) | What we take |
|---|---|---|
| Phone sheets (map Key and Layers, filters, the sign-in card) | Bottom Sheet Library: 11 Variants | Sheet shapes and states; its magenta is replaced by our colors |
| Side panel behavior | Minimalist sidebar component (a Figma Make file, so readable React source) | The icon strip plus the panel that collapses into it, and the collapse motion. Rebuilt, not copied: the source is dark-only with hard-coded colors, a fixed 800px height and no keyboard support |
| Side panel in both themes | Sidebars (Full Interactive) | A light and dark check for the side panel |

Icons stay Lucide (`lucide-react` is already a dependency); the 1,800-icon Figma pack was not adopted.

**Alternatives considered** (all 11 files were opened and compared against the wireframes' five patterns: the side panel, a full-width tab bar, tiles with small charts, centered frosted cards, phone bottom sheets):
- **DashStack free admin kit.** Capable, with two light and two dark styles, but it reads as a stock admin template (blue menu, pastel icon badges, busy layout). That is close to the problem a builder reported on the current site: nothing said what mattered.
- **One whole-app template.** None of the candidates covers the Profile's full-width tab bar or a map; the tab bar is designed by scaling up SnowUI's in-card tabs, and the map follows the brief's map rules (reference: the Cities: Skylines 2 OSM toolkit map, MIT).
- **Find Your Dream Home website template.** Built for home buyers, not builders, and its beige palette is close to the earth tones the owner already rejected for the site.
- **Glass-effect sidebar and frosted-glass card files.** Decorative glass over bright wallpaper; the one frosted card the design needs is a CSS `backdrop-filter`.
- **Charts kit (line, bar, pie, donut, radar, scatter, bubble, radial).** Kept as a styling reference for bar, line and scatter; SnowUI's charts are cleaner and consistent with the base. Pie, donut, radar and bubble have no slot in the wireframes.
- **Rendering real 3D with variables.** A Figma technique; the product's 3D is Mapbox extrusions on the real map.

**Why (evidence).** Read through the Figma tools (until the Starter plan's monthly cap on those calls) and then in the Figma desktop app, 2026-11-07. SnowUI's free file has light, dark and phone versions of its dashboard, but no saved color variables, so colors are taken from its screens and redrawn as our own tokens.

**Licensing.** All four adopted files are CC BY 4.0: the public About page must carry a credits line naming each file and author. This is a build task for the rewrite, not done yet.

**Revisit if:**
- Detailed mockups of the Profile Overview or Discovery show SnowUI's density does not fit the data (it was drawn for a sales dashboard).
- The owner moves to a paid Figma plan and wants components pulled straight into code (Code Connect); SnowUI's paid version has variables and components that would then matter.

**Numbers.** None measured; this item changes no code.
- **Not measured:** how builders read the new look. That waits for the clickable prototype test in the brief's plan (two or three builders on a real task).

---

## Item 74: the visual system: SnowUI's frame, the Coastal chart palette, black for this lot (2026-11-07)

**Decision: the new front end uses SnowUI's own colors for everything except charts.** Sampled from the SnowUI file in Figma and from the owner's screenshots of its light, dark and phone screens:

| Role | Light | Dark |
|---|---|---|
| Page | `#FFFFFF` | `#1C1C1C` |
| Blocks (chart and table panels) | `#F7F9FB` | `#282828` |
| Stat cards, alternating | `#E3F5FF`, `#E5ECF6` | same, with dark text |
| Text, the selected tab, this lot | Black `#1C1C1C` (SnowUI "Primary"), with 80/40/20/10/5% steps | White, same steps |
| Main button | Black, white label | Lavender `#C6C7F8`, dark label |
| Status | SnowUI's pills: pale fill, colored word (Recorded, In progress, Introduced, Open, Not a sale) | Same, tinted for dark |
| The analyst | The question box's lavender-to-blue edge and Send button (from SnowUI's chat screen), the only place that gradient appears | Same |
| Paid | One small black "Pro" tag on the Deep analysis tab | White tag |

Type is Inter (14px body, 12px labels, 18px answer sentence, 24px figures with tabular numbers); blocks have a 16px radius and 24px padding with 28px gaps; icons stay Lucide at 1.5 stroke.

**Decision: charts use the "Coastal" palette, taken from a reference palette the owner supplied, in this order:** Sapphire `#72B0AB`, Ballet Slipper `#FE9179`, Spruce `#355E58`, Pistachio `#B89D47`, Bubblegum `#FDC1B4`. Sapphire is the ordinary bar and context color; this lot (or the value the user chose) is black, white in dark mode. Charts with one to three series use the first three only.

**Decision: brief rule 9 ("color has jobs") is met partly by form.** "This property" is black in charts and a black outline with a white edge on maps; "you can click this" is the main button plus the shape of controls (selected tab, underlined links, hover fill), because SnowUI has no separate link color; "this costs money" is the Pro tag; status is the pills, always a word, never color alone.

**Decision: the side panel drops recent lots and chat history.** It is Search, Discovery, Saved, and Chat with a small menu for past chats. The owner's reasons: recent lots would push the chats out of view, neither list could be cleared, and chat gets its own history panel on the chat page. The analyst stays an on-demand drawer opened from the Ask icon in the top bar; SnowUI's permanent right-hand panel was not adopted (the brief already rules out a permanent chat or sources panel).

**Alternatives considered** (all shown to the owner on the private visual-system page, drafts 1-7):
- **A role-color scheme of our own on SnowUI's layout** (blue actions, orange lot, violet analyst). Rejected by the owner: it did not look like SnowUI.
- **SnowUI's own pastel chart colors.** Rejected: too similar to each other (the rent slider's two bands were hard to tell apart).
- **A high-saturation validated palette** (blue, orange, aqua, yellow...). Rejected: the colors did not harmonize.
- **Known palettes:** Tableau 10, Observable 10, Okabe-Ito. Superseded when the owner supplied reference palettes.
- **Two other palettes from the references:** "Teal and coral" (`#257C93`, `#EF5835`, `#E29F17`, ...) and "Dusk" (`#8F9AC9`, `#165B6D`, `#E29F17`, ...). Both pass the color-blind check more cleanly; the owner chose Coastal.

**Why (evidence).** Every palette was run through the data-viz palette validator (OKLab ΔE, Machado 2009 color-blind simulation), light surface `#F7F9FB` and dark surface `#282828`. Coastal's first three on every pair: normal vision ΔE 20.5 (pass, floor 15); color-blind ΔE 6.8 for Sapphire against Ballet Slipper (protan), in the 6-8 band that is acceptable only with secondary encoding. Its five-color order passes on neighbors for normal vision (worst ΔE 18.5).

**Rules that follow from Coastal's color-blind margin:**
- Every chart that uses both Sapphire and Ballet Slipper labels them directly (names beside the marks or a legend with values), never color alone.
- Scatter plots and maps use at most Sapphire, Spruce and black, or carry shape or labels as well.
- Spruce is weak on the dark background; keep it to third-series use.

**Still provisional:** the zoning colors (pastel family colors, darker as density rises; checked on every pair in light: `#B99C3A`, `#ED8A8E`, `#CDB7F6`, `#63A8CF`, `#A7E2B2`). They have not been reviewed next to Coastal and will be settled with the map mockups.

**Revisit if:**
- The clickable prototype shows builders missing what is clickable without a link color.
- A color-blind tester confuses Sapphire and Ballet Slipper even with labels; Teal and coral is the drop-in replacement.
- Detailed mockups need more than three chart colors often.

**Numbers.** None measured on the product; this item changes no code. The validator figures above are from 2026-11-07. Reproduce: `node <dataviz skill>/scripts/validate_palette.js "#72B0AB,#FE9179,#355E58" --mode light --surface "#F7F9FB" --pairs all` (and `--mode dark --surface "#282828"`).
- **Not measured:** how builders read the look (waits for the prototype test); contrast of every text and pill pairing (to check when the tokens are built).
