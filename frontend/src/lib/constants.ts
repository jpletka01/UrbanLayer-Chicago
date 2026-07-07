// Centralized UI copy, timings, and splash stats. Tune these without hunting
// through components.

export const SUGGESTIONS = [
  "What's going on near 1601 N Milwaukee Ave?",
  "Tell me about the property at 1550 N Wells St",
  "Can I open a bar at 2200 W Chicago Ave?",
  "Is Logan Square in a TIF district?",
];

// Splash-screen headline stats.
const commaFmt = (n: number) => n.toLocaleString("en-US");
const plusFmt = (n: number) => `${n}+`;
export const SPLASH_STATS = [
  { value: 25, label: "Data sources", format: plusFmt },
  { value: 14535, label: "Code sections", format: commaFmt },
  { value: 77, label: "Community areas" },
  { value: 12, label: "Regulatory layers" },
];

// Timings (ms).
export const TYPEWRITER_CHAR_DELAY_MS = 15;
export const AUTOCOMPLETE_DEBOUNCE_MS = 300;
export const HERO_SLIDE_INTERVAL_MS = 8000;
export const SOURCE_FLASH_MS = 850;

// Minimum input length before address autocomplete fires.
export const MIN_AUTOCOMPLETE_CHARS = 3;
