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
        // §2 — single neutral ramp. white/<opacity> neutrals are retired (migrated in Phase 2).
        dark: {
          bg: '#0d0d0d',               // app/page background
          surface: '#171717',          // default card/panel surface (opaque — no /80 fork)
          elevated: '#1f1f1f',         // raised within a surface: inputs, nested rows, badges
          hover: '#242424',            // NEW — interactive hover fill (replaces bg-white/5–10)
          'border-subtle': '#1f1f1f',  // low-contrast internal dividers
          border: '#2a2a2a',           // default hairline / card border
          'border-strong': '#383838',  // emphasis/hover/selected (replaces border-white/20–30)
        },
        accent: {
          DEFAULT: '#c96442',
          hover: '#d97a5a',
          muted: 'rgba(201, 100, 66, 0.15)',
        },
        text: {
          primary: '#eeeeee',
          secondary: '#a3a098',
          muted: '#6b6962',
          'on-accent': '#ffffff',      // NEW — text/icon on accent fills
        },
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
          '0%': { boxShadow: '0 0 0 0 rgba(201, 100, 66, 0.7)' },
          '70%': { boxShadow: '0 0 0 8px rgba(201, 100, 66, 0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(201, 100, 66, 0)' },
        },
        'dot-bounce': {
          '0%, 80%, 100%': { transform: 'translateY(0)' },
          '40%': { transform: 'translateY(-5px)' },
        },
        'text-glow': {
          '0%, 100%': { color: '#eeeeee' },
          '50%': { color: '#6b6962' },
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
