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
