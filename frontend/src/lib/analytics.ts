import i18n from "./i18n";

export interface TrendRow {
  category: string;
  currentCount: number;
  priorCount: number;
  /** null = prior month was 0 — the percentage is undefined (renders "new"). */
  changePercent: number | null;
  color: string;
}

export interface PieSlice {
  label: string;
  value: number;
  color: string;
}

function toYearMonth(dateStr: string): string | null {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return null;
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

function getCurrentYearMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function computeTrends<T>(
  records: T[],
  getDate: (r: T) => string,
  getCategory: (r: T) => string,
  getColor: (category: string) => string,
  capped = false,
): TrendRow[] {
  const byMonthAndCategory = new Map<string, Map<string, number>>();

  for (const r of records) {
    const ym = toYearMonth(getDate(r));
    if (!ym) continue;
    const cat = getCategory(r);
    if (!byMonthAndCategory.has(ym)) byMonthAndCategory.set(ym, new Map());
    const catMap = byMonthAndCategory.get(ym)!;
    catMap.set(cat, (catMap.get(cat) ?? 0) + 1);
  }

  let months = [...byMonthAndCategory.keys()].sort();
  // Rows arrive date-DESC; a row-capped fetch truncates the OLDEST month
  // mid-month, so comparing against it fabricates an increase — drop it.
  if (capped && months.length) {
    byMonthAndCategory.delete(months[0]);
    months = months.slice(1);
  }
  if (months.length < 2) return [];

  const currentCalendar = getCurrentYearMonth();
  let currentMonth: string;
  let priorMonth: string;

  if (months[months.length - 1] === currentCalendar && months.length >= 3) {
    currentMonth = months[months.length - 2];
    priorMonth = months[months.length - 3];
  } else {
    currentMonth = months[months.length - 1];
    priorMonth = months[months.length - 2];
  }

  const currentData = byMonthAndCategory.get(currentMonth) ?? new Map<string, number>();
  const priorData = byMonthAndCategory.get(priorMonth) ?? new Map<string, number>();

  const allCategories = new Set([...currentData.keys(), ...priorData.keys()]);
  const rows: TrendRow[] = [];

  for (const cat of allCategories) {
    const curr = currentData.get(cat) ?? 0;
    const prev = priorData.get(cat) ?? 0;
    // prior 0 → percentage undefined, not "+100%"; null renders as "new".
    const change = prev === 0 ? null : ((curr - prev) / prev) * 100;
    rows.push({
      category: cat,
      currentCount: curr,
      priorCount: prev,
      changePercent: change === null ? null : Math.round(change),
      color: getColor(cat),
    });
  }

  rows.sort((a, b) => b.currentCount - a.currentCount);
  return rows;
}

export function computePieSlices<T>(
  records: T[],
  getCategory: (r: T) => string,
  getColor: (category: string) => string,
): PieSlice[] {
  const counts = new Map<string, number>();
  for (const r of records) {
    const cat = getCategory(r);
    counts.set(cat, (counts.get(cat) ?? 0) + 1);
  }

  const slices: PieSlice[] = [];
  for (const [label, value] of counts) {
    slices.push({ label, value, color: getColor(label) });
  }

  slices.sort((a, b) => b.value - a.value);
  return slices;
}

export function getTrendMonthLabels<T>(
  records: T[],
  getDate: (r: T) => string,
  capped = false,
): { current: string; prior: string } | null {
  const months = new Set<string>();
  for (const r of records) {
    const ym = toYearMonth(getDate(r));
    if (ym) months.add(ym);
  }
  let sorted = [...months].sort();
  if (capped && sorted.length) sorted = sorted.slice(1); // mirror computeTrends
  if (sorted.length < 2) return null;

  const currentCalendar = getCurrentYearMonth();
  let currentMonth: string;
  let priorMonth: string;

  if (sorted[sorted.length - 1] === currentCalendar && sorted.length >= 3) {
    currentMonth = sorted[sorted.length - 2];
    priorMonth = sorted[sorted.length - 3];
  } else {
    currentMonth = sorted[sorted.length - 1];
    priorMonth = sorted[sorted.length - 2];
  }

  const fmt = (ym: string) => {
    const [y, m] = ym.split("-");
    const date = new Date(Number(y), Number(m) - 1);
    const locale = i18n.language === "es" ? "es-US" : "en-US";
    return date.toLocaleDateString(locale, { month: "short", year: "2-digit" });
  };

  return { current: fmt(currentMonth), prior: fmt(priorMonth) };
}
