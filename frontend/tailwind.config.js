/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        'bg-dark': '#090d16',
        dark: {
          bg: '#0d0d0d',
          surface: '#171717',
          elevated: '#1f1f1f',
          border: '#2a2a2a',
          'border-subtle': '#1f1f1f',
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
        },
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
      },
      animation: {
        'fade-in': 'fade-in 2s ease-in-out forwards',
        'blink': 'blink 1s step-end infinite',
      },
    },
  },
  plugins: [],
};
