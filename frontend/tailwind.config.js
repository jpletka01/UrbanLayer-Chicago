/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // §7 — Inter body/UI, Space Grotesk display (h1/section), IBM Plex Mono for data.
        // Spec named only Fraunces's fallback; the Space Grotesk + mono fallbacks below
        // are derived (grotesque → sans fallback; mono → system mono). [judgment call]
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Space Grotesk"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
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
        // Elevation inverts between modes (§4): near-none in dark, real soft shadow in light.
        card: 'var(--shadow-card)',
        modal: 'var(--shadow-modal)',
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
      },
      keyframes: {
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
      },
      animation: {
        'fade-in': 'fade-in 2s ease-in-out forwards',
        'blink': 'blink 1s step-end infinite',
        'flash': 'flash 0.8s ease-out',
        'dot-bounce': 'dot-bounce 1.4s ease-in-out infinite',
        'text-glow': 'text-glow 2s ease-in-out infinite',
        'trace-in': 'trace-in 0.2s ease-out both',
        'slide-up': 'slide-up 0.3s ease-out forwards',
      },
    },
  },
  plugins: [],
};
