// What a saved lot's "what changed" lines say and where they open (Saved, decision Item 119). Pure: the page passes
// `t` and formatters; the backend decides what changed and what couldn't be checked.
import type { LucideIcon } from "lucide-react";
import { FileClock, Hammer, Landmark, Layers, Ruler, Tag, TriangleAlert } from "lucide-react";
import type { SavedChange } from "../../lib/api";
import { humanizeShoutyCase } from "../../lib/format";
import { lotHref, type RememberedLot } from "../home/lotMemory";

type T = (key: string, opts?: Record<string, unknown>) => string;

export interface ChangeLine {
  icon: LucideIcon;
  text: string;
  /** "YYYY-MM-DD", or null when the change has no date of its own. */
  date: string | null;
  href: string;
  /** An official record outside UrbanLayer (opens in a new tab). */
  external: boolean;
  tone: "blue" | "yellow" | "purple" | "gray";
}

// The City's records are in capitals ("MAINTAIN OR REPAIR HYDRANT"); they read as sentences here.
const clip = (s: string | null | undefined, n = 70) => {
  const v = humanizeShoutyCase((s ?? "").replace(/\s+/g, " ").trim());
  return v.length > n ? `${v.slice(0, n - 1).trimEnd()}…` : v;
};

/** One change, worded, with its icon and where it opens. */
export function changeLine(c: SavedChange, lot: Pick<RememberedLot, "pin" | "address">, t: T, money: (v: number) => string): ChangeLine {
  const profile = (tab: string) => `${lotHref(lot)}&tab=${tab}`;
  switch (c.kind) {
    case "sale":
      return { icon: Tag, tone: "blue", date: c.date, href: profile("history"), external: false,
        text: c.price ? t("saved.change.soldFor", { price: money(c.price) }) : t("saved.change.sold") };
    case "permit":
      return { icon: Hammer, tone: "blue", date: c.date, href: profile("history"), external: false,
        text: c.cost
          ? t("saved.change.permitCost", { kind: clip(c.permit_type || c.description, 40), cost: money(c.cost) })
          : t("saved.change.permit", { kind: clip(c.permit_type || c.description, 40) }) };
    case "violation":
      return { icon: TriangleAlert, tone: "yellow", date: c.date, href: profile("history"), external: false,
        text: t("saved.change.violation", { what: clip(c.description || c.code, 60) }) };
    case "rezoning_filed":
      return { icon: FileClock, tone: "purple", date: c.date, href: c.url, external: true,
        text: t("saved.change.rezoningFiled", { record: c.record }) };
    case "district":
      return { icon: Landmark, tone: "purple", date: c.date ?? null, href: c.url || profile("build"), external: !!c.url,
        text: t("saved.change.district", { from: c.old, to: c.new }) };
    case "overlay":
      return { icon: Layers, tone: "purple", date: null, href: profile("build"), external: false,
        text: c.change === "added"
          ? t("saved.change.overlayAdded", { name: c.name || t(`chat:sinceThen.layers.${c.layer}`, { defaultValue: c.layer }) })
          : t("saved.change.overlayRemoved", { name: t(`chat:sinceThen.layers.${c.layer}`, { defaultValue: c.layer }) }) };
    case "standards":
      return { icon: Ruler, tone: "purple", date: null, href: profile("build"), external: false,
        text: t("saved.change.standards", { zone: c.zone_class ?? "" }) };
    case "map_amendment":
      return { icon: Landmark, tone: "purple", date: c.date ?? null, href: c.url || profile("build"), external: !!c.url,
        text: t("saved.change.rezoningPassed", { record: c.record ?? "" }) };
    case "designation":
      return { icon: Landmark, tone: "purple", date: c.date ?? null, href: c.url || profile("build"), external: !!c.url,
        text: t("saved.change.designation", { name: c.name ?? c.record ?? "" }) };
  }
}

/** The sources a check couldn't read, in words ("sales and permits"). */
export function uncheckedWords(keys: string[], t: T): string {
  const words = keys.map((k) => t(`saved.unchecked.${k}`, { defaultValue: k }));
  if (words.length <= 1) return words[0] ?? "";
  return `${words.slice(0, -1).join(", ")} ${t("saved.and")} ${words[words.length - 1]}`;
}

/** Run `fn` with at most `n` running at once (the page checks lots as they scroll in). */
export function limiter(n: number) {
  let running = 0;
  const queue: Array<() => void> = [];
  const next = () => {
    if (running >= n) return;
    const job = queue.shift();
    if (!job) return;
    running += 1;
    job();
  };
  return function run<R>(fn: () => Promise<R>): Promise<R> {
    return new Promise<R>((resolve, reject) => {
      queue.push(() => {
        fn().then(resolve, reject).finally(() => { running -= 1; next(); });
      });
      next();
    });
  };
}
