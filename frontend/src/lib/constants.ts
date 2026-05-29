// Centralized UI copy, timings, and splash stats. Tune these without hunting
// through components.

export const SUGGESTIONS = [
  "What's going on near 2400 N Milwaukee Ave?",
  "Crime trends in Wicker Park last 90 days",
  "Can I open a bar in a residential district?",
  "Top 311 complaints in Logan Square",
];

// Splash-screen headline stats.
export const SPLASH_STATS = [
  { value: "14,628", label: "Code sections" },
  { value: "5", label: "Live datasets" },
  { value: "77", label: "Community areas" },
];

// Timings (ms).
export const TYPEWRITER_CHAR_DELAY_MS = 15;
export const AUTOCOMPLETE_DEBOUNCE_MS = 300;
export const HERO_SLIDE_INTERVAL_MS = 8000;
export const SOURCE_FLASH_MS = 850;

// Minimum input length before address autocomplete fires.
export const MIN_AUTOCOMPLETE_CHARS = 3;
