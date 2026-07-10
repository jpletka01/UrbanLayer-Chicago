// Centralized UI timings and splash stats. Tune these without hunting
// through components.

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
export const SOURCE_FLASH_MS = 850;

// Minimum input length before address autocomplete fires.
export const MIN_AUTOCOMPLETE_CHARS = 3;
