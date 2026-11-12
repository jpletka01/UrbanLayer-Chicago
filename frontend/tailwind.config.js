/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // Bento Pro type — Inter body/UI, Inter Tight display (hero/section headings),
        // JetBrains Mono for data/PINs/code (IBM Plex Mono kept as fallback).
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Inter Tight"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        // §2 — single neutral ramp, now CSS-var-backed for light/dark theming (2026-06-29,
        // see guides/light-dark-theming.md). Class names are UNCHANGED (`bg-dark-surface`,
        // `text-text-primary`, …) — only the backing flips. Each var holds an RGB channel
        // triplet so Tailwind's `<alpha-value>` opacity utilities (`bg-dark-surface/80`) keep
        // working. Values live in src/index.css (:root = dark default, [data-theme=light]).
        // The `dark-*` key names are now a slight misnomer in light mode (internal only).
        dark: {
          bg: 'rgb(var(--bg) / <alpha-value>)',                          // app/page background
          surface: 'rgb(var(--surface) / <alpha-value>)',               // default card/panel surface
          elevated: 'rgb(var(--elevated) / <alpha-value>)',             // raised: inputs, nested rows
          hover: 'rgb(var(--hover) / <alpha-value>)',                   // interactive hover fill
          'border-subtle': 'rgb(var(--border-subtle) / <alpha-value>)', // internal dividers
          border: 'rgb(var(--border) / <alpha-value>)',                 // default hairline / border
          'border-strong': 'rgb(var(--border-strong) / <alpha-value>)', // emphasis/hover/selected
        },
        accent: {
          DEFAULT: 'rgb(var(--accent) / <alpha-value>)',               // brand / selected / focus / outline
          hover: 'rgb(var(--accent-hover) / <alpha-value>)',
          // text/link variant — lighter on dark / darker on light so accent text clears AA on
          // both (the accent FILL stays vivid). Use this for links, never `text-accent` on dark.
          text: 'rgb(var(--accent-text) / <alpha-value>)',
          muted: 'rgb(var(--accent) / var(--accent-muted-a))',          // selected-fill, alpha flips
        },
        // Action hierarchy (problem 3) — reads by FORM first (fill > outline > text > neutral),
        // hue second. Primary = filled `action`; Secondary = `border-accent` + `text-accent-text`;
        // Tertiary = `text-link` only; Inert = neutral ramp. Aliases of the accent var so the
        // class name documents intent at the call site.
        action: {
          // DECOUPLED from --accent: a slightly deeper azure so white labels keep AA on the
          // filled button, while accent/links/outlines stay bright azure.
          DEFAULT: 'rgb(var(--action-primary) / <alpha-value>)',       // bg-action — primary fill
          hover: 'rgb(var(--action-primary-hover) / <alpha-value>)',   // hover:bg-action-hover
          fg: 'rgb(var(--text-on-accent) / <alpha-value>)',            // text-action-fg (white)
        },
        link: 'rgb(var(--accent-text) / <alpha-value>)',               // text-link (= accent-text)
        // Terracotta premium highlight — the only warm in the chrome; reserved for the paid report.
        highlight: {
          DEFAULT: 'rgb(var(--highlight) / <alpha-value>)',            // text/icon
          fill: 'rgb(var(--highlight-fill) / <alpha-value>)',          // badge fill
          fg: 'rgb(var(--highlight-fg) / <alpha-value>)',              // white on fill
        },
        text: {
          primary: 'rgb(var(--text-primary) / <alpha-value>)',
          secondary: 'rgb(var(--text-secondary) / <alpha-value>)',
          muted: 'rgb(var(--text-muted) / <alpha-value>)',
          'on-accent': 'rgb(var(--text-on-accent) / <alpha-value>)',    // text/icon on accent fills
          disabled: 'rgb(var(--text-disabled) / <alpha-value>)',
        },
        // ── Semantic role layer (decision Item 49) ─────────────────────────────────────────
        // Components pick a ROLE: `action` (orange: clickable only, ≤1 solid per viewport),
        // `premium` (violet: costs money only), `status-*` (genuine state). A test fails on raw
        // palette classes (amber-400, …) in the Profile's components. `subtle` = the tinted fill a
        // StatusLabel sits on; DEFAULT = its text/glyph.
        premium: {
          DEFAULT: 'rgb(var(--highlight) / <alpha-value>)',
          fill: 'rgb(var(--highlight-fill) / <alpha-value>)',
          fg: 'rgb(var(--highlight-fg) / <alpha-value>)',
        },
        status: {
          success: { DEFAULT: 'rgb(var(--status-success) / <alpha-value>)', subtle: 'rgb(var(--status-success) / 0.12)' },
          warning: { DEFAULT: 'rgb(var(--status-warning) / <alpha-value>)', subtle: 'rgb(var(--status-warning) / 0.14)' },
          danger: { DEFAULT: 'rgb(var(--status-danger) / <alpha-value>)', subtle: 'rgb(var(--status-danger) / 0.12)' },
          info: { DEFAULT: 'rgb(var(--status-info) / <alpha-value>)', subtle: 'rgb(var(--status-info) / 0.12)' },
          neutral: { DEFAULT: 'rgb(var(--status-neutral) / <alpha-value>)', subtle: 'rgb(var(--status-neutral) / 0.12)' },
        },
        // ── The new UI (decision Items 74, 76): defined ONLY inside `.ui-next` (src/ui-next/ui-next.css),
        // so an `nx-*` class outside the preview resolves to nothing. Used only under src/ui-next/
        // (the isolation test checks both).
        nx: {
          page: 'rgb(var(--nx-page) / <alpha-value>)',
          block: 'rgb(var(--nx-block) / <alpha-value>)',
          'stat-a': 'rgb(var(--nx-stat-a) / <alpha-value>)',
          'stat-b': 'rgb(var(--nx-stat-b) / <alpha-value>)',
          'card-ink': 'rgb(var(--nx-card-ink) / <alpha-value>)',
          ink: 'rgb(var(--nx-ink) / <alpha-value>)',
          'on-ink': 'rgb(var(--nx-on-ink) / <alpha-value>)',
          primary: 'rgb(var(--nx-primary) / <alpha-value>)',
          'primary-fg': 'rgb(var(--nx-primary-fg) / <alpha-value>)',
          lot: 'rgb(var(--nx-lot) / <alpha-value>)',
          'pill-purple': 'rgb(var(--nx-pill-purple) / <alpha-value>)',
          'pill-purple-bg': 'rgb(var(--nx-pill-purple-bg) / <alpha-value>)',
          'pill-green': 'rgb(var(--nx-pill-green) / <alpha-value>)',
          'pill-green-bg': 'rgb(var(--nx-pill-green-bg) / <alpha-value>)',
          'pill-blue': 'rgb(var(--nx-pill-blue) / <alpha-value>)',
          'pill-blue-bg': 'rgb(var(--nx-pill-blue-bg) / <alpha-value>)',
          'pill-yellow': 'rgb(var(--nx-pill-yellow) / <alpha-value>)',
          'pill-yellow-bg': 'rgb(var(--nx-pill-yellow-bg) / <alpha-value>)',
          'pill-red': 'rgb(var(--nx-pill-red) / <alpha-value>)',
          'pill-red-bg': 'rgb(var(--nx-pill-red-bg) / <alpha-value>)',
          'chart-1': 'rgb(var(--nx-chart-1) / <alpha-value>)',
          'chart-2': 'rgb(var(--nx-chart-2) / <alpha-value>)',
          'chart-3': 'rgb(var(--nx-chart-3) / <alpha-value>)',
          'chart-4': 'rgb(var(--nx-chart-4) / <alpha-value>)',
          'chart-5': 'rgb(var(--nx-chart-5) / <alpha-value>)',
        },
        // Themed semantic state tones (§6) — replace the static Tailwind emerald/rose/amber-400
        // refs in Phase 3. -400 in dark, -700 in light (the only AA failures light introduces).
        state: {
          positive: 'rgb(var(--state-positive) / <alpha-value>)',
          negative: 'rgb(var(--state-negative) / <alpha-value>)',
          warning: 'rgb(var(--state-warning) / <alpha-value>)',
        },
      },
      boxShadow: {
        // Elevation inverts between modes: subtle in dark, real soft shadow in light.
        card: 'var(--shadow-card)',
        modal: 'var(--shadow-modal)',
        // Bento accent glow — hover lift on interactive tiles / brand CTA halo.
        glow: 'var(--glow-accent)',
      },
      borderRadius: {
        // Bento tile radius (spec radius.md: card 32px desktop / 20px mobile). Applied by the
        // Card/Modal primitives; stock Tailwind radii stay intact for everything else.
        bento: '1.75rem',       // 28px — big bento tiles
        'bento-sm': '1.25rem',  // 20px — compact/mobile tiles
      },
      backgroundImage: {
        // Brand CTA gradient (buttons.md) — warm orange blend, dark label on top.
        'brand-gradient': 'linear-gradient(135deg, #f9a474 0%, #f7b38e 55%, #fcd2b7 100%)',
        'brand-gradient-hover': 'linear-gradient(135deg, #f39a67 0%, #f9a474 55%, #f7b38e 100%)',
      },
      // §1 — named type scale (size · line-height · weight · tracking). Additive: the stock
      // Tailwind sizes remain until pages are migrated (Phase 2). Responsive steps use
      // clamp() so one token spans the spec's mobile→desktop range. `overline` pairs with
      // the `uppercase` utility (text-transform can't live in a fontSize token).
      fontSize: {
        display: ['clamp(2.25rem, 1.82rem + 1.85vw, 3rem)', { lineHeight: '1.05', fontWeight: '600', letterSpacing: '-0.02em' }],
        stat: ['clamp(1.5rem, 1.07rem + 1.85vw, 2.25rem)', { lineHeight: '1.1', fontWeight: '600', letterSpacing: '-0.01em' }],
        section: ['clamp(1.5rem, 1.28rem + 0.92vw, 1.875rem)', { lineHeight: '1.2', fontWeight: '600', letterSpacing: '-0.01em' }],
        subtitle: ['1.125rem', { lineHeight: '1.3', fontWeight: '600' }],
        lead: ['1rem', { lineHeight: '1.55', fontWeight: '400' }],
        title: ['0.875rem', { lineHeight: '1.4', fontWeight: '600' }],
        body: ['0.875rem', { lineHeight: '1.5', fontWeight: '400' }],
        caption: ['0.75rem', { lineHeight: '1.45', fontWeight: '400' }],
        micro: ['0.6875rem', { lineHeight: '1.45', fontWeight: '500' }],
        overline: ['0.6875rem', { lineHeight: '1.2', fontWeight: '600', letterSpacing: '0.08em' }],
        // The new UI's two extra steps (Item 74): the 18px answer sentence and the 24px figure.
        'nx-answer': ['1.125rem', { lineHeight: '1.625rem', fontWeight: '600' }],
        'nx-figure': ['1.5rem', { lineHeight: '2.25rem', fontWeight: '600' }],
      },
      keyframes: {
        // The new landing (Phase 8, owner 2026-11-12): the hero scene drifts slowly; Discovery's block grid glows a few
        // blocks at a time. Both stop under reduced motion (motion-safe: in the markup).
        'scene-drift': {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '50%': { transform: 'translate(-36px, -10px) scale(1.05)' },
        },
        'block-glow': {
          '0%, 40%, 60%, 100%': { filter: 'none' },
          '50%': { filter: 'brightness(1.35) saturate(1.25)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'blink': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        'flash': {
          '0%': { boxShadow: '0 0 0 0 rgb(var(--accent) / 0.7)' },
          '70%': { boxShadow: '0 0 0 8px rgb(var(--accent) / 0)' },
          '100%': { boxShadow: '0 0 0 0 rgb(var(--accent) / 0)' },
        },
        'dot-bounce': {
          '0%, 80%, 100%': { transform: 'translateY(0)' },
          '40%': { transform: 'translateY(-5px)' },
        },
        'text-glow': {
          '0%, 100%': { color: 'rgb(var(--text-primary))' },
          '50%': { color: 'rgb(var(--text-muted))' },
        },
        'trace-in': {
          '0%': { opacity: '0', transform: 'translateY(-3px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(100%)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        // Idle search field: gently breathe from the resting shadow to the accent
        // glow (same box-shadow the field holds on hover), so it draws the eye but
        // lands on the identical orange once hovered/focused. Both endpoints are
        // 2-layer, theme-aware shadows so the interpolation is smooth.
        'search-pulse': {
          '0%, 100%': { boxShadow: 'var(--shadow-card)' },
          '50%': { boxShadow: 'var(--glow-accent)' },
        },
      },
      animation: {
        'scene-drift': 'scene-drift 26s ease-in-out infinite',
        'block-glow': 'block-glow 9s ease-in-out infinite',
        'fade-in': 'fade-in 2s ease-in-out forwards',
        'blink': 'blink 1s step-end infinite',
        'flash': 'flash 0.8s ease-out',
        'dot-bounce': 'dot-bounce 1.4s ease-in-out infinite',
        'text-glow': 'text-glow 2s ease-in-out infinite',
        'trace-in': 'trace-in 0.2s ease-out both',
        'slide-up': 'slide-up 0.3s ease-out forwards',
        'search-pulse': 'search-pulse 2.6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
