// DEV-ONLY MOCKUP (decision Item 129, second pass after the owner's review 2026-11-17): how anyone suggests a
// correction to a lot's building facts from the Discovery map's lot card. Not production code: the route exists only
// under `import.meta.env.DEV` (`DEV_PAGES` in pages.ts), so the production build drops this file and its images.
// Built on the real card as it is on #242's branch (ExploreMap.tsx `LotCard`: address, lot, room, a dark Open profile
// button, Street View and Google Maps side by side), over screenshots of the real Discovery map (`mock/*.jpg`, taken
// from the local stack). The strings live here until the build PRs move them into the `next` catalogs.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ArrowLeft, ArrowRight, Check, CircleCheck, MapPinned, PencilLine, PersonStanding, UserCheck, X } from "lucide-react";
import { STROKE } from "../icons";
import backDesktopLight from "./mock/back-desktop-light.jpg";
import backDesktopDark from "./mock/back-desktop-dark.jpg";
import backPhoneLight from "./mock/back-phone-light.jpg";
import backPhoneDark from "./mock/back-phone-dark.jpg";

type Lang = "en" | "es";
type Theme = "light" | "dark";

// es-MX, usted register.
const S = {
  en: {
    suggest: "Suggest a correction", sentTip: "Correction sent, in review",
    q: "What's wrong with this building?", back: "Back to the lot", close: "Close",
    chips: { stories: "Stories", area: "Floor area", gone: "No building now", there: "There's a building", condo: "Not a condo", isCondo: "It's a condo", other: "Other" },
    storiesUnit: "stories", storiesLabel: "Number of stories", areaHigh: "Too high", areaLow: "Too low",
    note: "Add a note (optional)", send: "Send", thanks: "Thanks, we'll review it.",
    reviewedTip: "Floor area from a reviewed user report (3 stories)",
    open: "Open profile", streetView: "Street View", maps: "Google Maps",
    lot: "4,800 sq ft lot", room: (v: string) => `Room to build: ${v} sq ft`,
  },
  es: {
    suggest: "Sugerir una corrección", sentTip: "Corrección enviada, en revisión",
    q: "¿Qué está mal con este edificio?", back: "Volver al terreno", close: "Cerrar",
    chips: { stories: "Pisos", area: "Superficie", gone: "Ya no hay edificio", there: "Hay un edificio", condo: "No es condominio", isCondo: "Es condominio", other: "Otra cosa" },
    storiesUnit: "pisos", storiesLabel: "Número de pisos", areaHigh: "Muy alta", areaLow: "Muy baja",
    note: "Agregue una nota (opcional)", send: "Enviar", thanks: "Gracias, lo revisaremos.",
    reviewedTip: "Superficie de un reporte de usuario revisado (3 pisos)",
    open: "Abrir ficha", streetView: "Street View", maps: "Google Maps",
    lot: "Terreno de 4,800 pies²", room: (v: string) => `Espacio para construir: ${v} pies²`,
  },
} as const;
type Strings = (typeof S)[Lang];

// The lot the screenshots show clicked (1850 N Leavitt St, its real figures on the local index), with a made-up
// estimate of 2 stories for the mockup.
const LOT = { title: "1850 N Leavitt St", room: 1588, roomReviewed: 410, stories: 2, condo: false, hasBuilding: true };

type Chip = "stories" | "area" | "gone" | "condo" | "other";
type Form = { chips: Chip[]; stories: string; area: "high" | "low" | null; note: string };
const EMPTY: Form = { chips: [], stories: "", area: null, note: "" };
type Mode = "card" | "form" | "sent" | "afterSend" | "reviewed";

const ICON_BTN = "grid h-7 w-7 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon";
const CARD = "w-[17.5rem] max-w-full rounded-2xl bg-nx-page p-4 text-caption text-nx-ink shadow-[0_8px_32px_rgb(0_0_0/0.18)]";

/** An icon button with its name as a tooltip on hover and focus (never hover-only: the click is the action). */
function IconTool({ label, onClick, children, showTip = false, pressed }: { label: string; onClick?: () => void; children: ReactNode; showTip?: boolean; pressed?: boolean }) {
  return (
    <span className="group relative">
      <button type="button" aria-label={label} aria-pressed={pressed} onClick={onClick} className={ICON_BTN}>{children}</button>
      <span role="tooltip" className={`pointer-events-none absolute right-0 top-full z-20 mt-1 whitespace-nowrap rounded-md bg-nx-ink px-2 py-1 text-[11px] text-nx-on-ink ${showTip ? "block" : "hidden group-hover:block group-focus-within:block"}`}>{label}</span>
    </span>
  );
}

// ── The form, in the card's place ─────────────────────────────────────────────────────────────────────────────────
function SuggestForm({ s, initial = EMPTY, onBack, onSend }: { s: Strings; initial?: Form; onBack?: () => void; onSend?: () => void }) {
  const [f, setF] = useState<Form>(initial);
  const storiesRef = useRef<HTMLInputElement>(null);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const on = (c: Chip) => f.chips.includes(c);
  const toggle = (c: Chip) => setF((x) => {
    let chips = on(c) ? x.chips.filter((y) => y !== c) : [...x.chips, c];
    if (c === "gone" && chips.includes("gone")) chips = chips.filter((y) => y !== "stories" && y !== "area"); // moot
    if ((c === "stories" || c === "area") && chips.includes(c)) chips = chips.filter((y) => y !== "gone");
    return { ...x, chips };
  });
  const last = f.chips[f.chips.length - 1];
  useEffect(() => {
    if (last === "stories") storiesRef.current?.focus();
    if (last === "other") noteRef.current?.focus();
  }, [last]);
  const chips: Array<[Chip, string]> = [
    ...(LOT.hasBuilding ? [["stories", s.chips.stories], ["area", s.chips.area], ["gone", s.chips.gone]] as Array<[Chip, string]> : [["gone", s.chips.there]] as Array<[Chip, string]>),
    ["condo", LOT.condo ? s.chips.condo : s.chips.isCondo],
    ["other", s.chips.other],
  ];
  const ready = f.chips.length > 0 && (!on("stories") || /^\d{1,3}$/.test(f.stories)) && (!on("area") || f.area != null);
  return (
    <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (ready) onSend?.(); }}>
      <div className="flex items-start gap-1 pr-6">
        {onBack && <button type="button" aria-label={s.back} onClick={onBack} className={`-ml-1.5 shrink-0 ${ICON_BTN}`}><ArrowLeft aria-hidden className="h-4 w-4" strokeWidth={STROKE} /></button>}
        <p className="pt-0.5 text-body font-semibold leading-snug">{s.q}</p>
      </div>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label={s.q}>
        {chips.map(([c, label]) => (
          <button key={c} type="button" aria-pressed={on(c)} onClick={() => toggle(c)}
            className={`inline-flex h-8 items-center gap-1 rounded-full px-3 touch-target ${on(c) ? "bg-nx-ink font-medium text-nx-on-ink" : "bg-nx-ink/5 hover:bg-nx-ink/10"}`}>
            {on(c) && <Check aria-hidden className="h-3.5 w-3.5" strokeWidth={2.25} />}{label}
          </button>
        ))}
      </div>
      {(on("stories") || on("area")) && (
        <div className="flex flex-col gap-2 rounded-lg bg-nx-ink/5 p-2">
          {on("stories") && (
            <label className="flex items-center gap-2">
              <input ref={storiesRef} type="text" inputMode="numeric" pattern="[0-9]*" maxLength={3} aria-label={s.storiesLabel}
                value={f.stories} placeholder={String(LOT.stories)} onFocus={(e) => e.currentTarget.select()}
                onChange={(e) => setF((x) => ({ ...x, stories: e.target.value.replace(/\D/g, "") }))}
                className="h-8 w-14 rounded-md bg-nx-page text-center text-body font-semibold tabular-nums text-nx-ink ring-1 ring-nx-ink/15 placeholder:font-normal placeholder:text-nx-ink/40 focus:outline-none focus:ring-nx-ink/60" />
              <span>{s.storiesUnit}</span>
            </label>
          )}
          {on("area") && (
            <div className="grid grid-cols-2 gap-1 rounded-md bg-nx-page p-0.5 ring-1 ring-nx-ink/15">
              {([["high", s.areaHigh], ["low", s.areaLow]] as const).map(([k, label]) => (
                <button key={k} type="button" aria-pressed={f.area === k} onClick={() => setF((x) => ({ ...x, area: k }))}
                  className={`h-7 rounded ${f.area === k ? "bg-nx-ink font-medium text-nx-on-ink" : "hover:bg-nx-ink/5"}`}>{label}</button>
              ))}
            </div>
          )}
        </div>
      )}
      <textarea ref={noteRef} rows={2} maxLength={280} value={f.note} placeholder={s.note} aria-label={s.note}
        onChange={(e) => setF((x) => ({ ...x, note: e.target.value }))}
        className="resize-none rounded-lg bg-nx-ink/5 px-3 py-2 text-nx-ink placeholder:text-nx-ink/50 focus:outline-none focus:ring-1 focus:ring-nx-ink/60" />
      <button type="submit" disabled={!ready}
        className="inline-flex h-9 w-full items-center justify-center rounded-lg bg-nx-ink px-3 font-semibold text-nx-on-ink disabled:opacity-30 touch-target">{s.send}</button>
    </form>
  );
}

// ── The real map card (#242), with the pencil beside the close button ─────────────────────────────────────────────
function MockLotCard({ lang, mode: start, interactive = false, initial, showTip = false }: { lang: Lang; mode: Mode; interactive?: boolean; initial?: Form; showTip?: boolean }) {
  const s = S[lang];
  const [mode, setMode] = useState<Mode>(start);
  const n = (v: number) => v.toLocaleString(lang === "es" ? "es-MX" : "en-US");
  useEffect(() => {
    if (interactive && mode === "sent") { const id = setTimeout(() => setMode("afterSend"), 2200); return () => clearTimeout(id); }
  }, [interactive, mode]);
  const close = <span className="absolute right-2 top-2"><IconTool label={s.close} onClick={interactive ? () => setMode(mode === "form" || mode === "sent" ? (mode === "sent" ? "afterSend" : "card") : mode) : undefined}><X aria-hidden className="h-4 w-4" strokeWidth={STROKE} /></IconTool></span>;

  if (mode === "form") return <div className={`relative ${CARD}`}>{close}<SuggestForm s={s} initial={initial} onBack={interactive ? () => setMode("card") : () => {}} onSend={interactive ? () => setMode("sent") : undefined} /></div>;
  if (mode === "sent") {
    return (
      <div className={`relative ${CARD}`} role="status">
        {close}
        <p className="flex items-center gap-2 pr-6 text-body font-medium"><CircleCheck aria-hidden className="h-5 w-5 shrink-0 text-nx-pill-green" strokeWidth={STROKE} />{s.thanks}</p>
      </div>
    );
  }
  return (
    <div className={`relative ${CARD}`}>
      <div className="absolute right-2 top-2 flex items-center">
        {mode === "afterSend" ? (
          <IconTool label={s.sentTip} showTip={showTip}><Check aria-hidden className="h-4 w-4 nx-muted" strokeWidth={STROKE} /></IconTool>
        ) : mode !== "reviewed" ? (
          <IconTool label={s.suggest} showTip={showTip} onClick={interactive ? () => setMode("form") : undefined}><PencilLine aria-hidden className="h-4 w-4 nx-muted" strokeWidth={STROKE} /></IconTool>
        ) : null}
        <IconTool label={s.close}><X aria-hidden className="h-4 w-4" strokeWidth={STROKE} /></IconTool>
      </div>
      <div className="flex flex-col gap-1.5 pr-14">
        <p className="text-body font-semibold">{LOT.title}</p>
        <p className="nx-muted">{s.lot}</p>
        <p className="group relative flex items-center gap-1">
          {s.room(n(mode === "reviewed" ? LOT.roomReviewed : LOT.room))}
          {mode === "reviewed" && (
            <>
              <span className="inline-flex" tabIndex={0} aria-label={s.reviewedTip}>
                <UserCheck aria-hidden className="h-3.5 w-3.5 nx-muted" strokeWidth={STROKE} />
              </span>
              <span role="tooltip" className={`pointer-events-none absolute left-0 top-full z-20 mt-1 w-[13rem] rounded-md bg-nx-ink px-2 py-1 text-[11px] text-nx-on-ink ${showTip ? "block" : "hidden group-hover:block group-focus-within:block"}`}>{s.reviewedTip}</span>
            </>
          )}
        </p>
      </div>
      <div className="mt-3 flex flex-col gap-2">
        <button type="button" className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-nx-ink px-3 font-semibold text-nx-on-ink touch-target">
          {s.open}<ArrowRight aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
        </button>
        <div className="grid grid-cols-2 gap-2">
          <span className="inline-flex h-9 min-w-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg bg-nx-ink/5 px-2 font-medium"><PersonStanding aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />{s.streetView}</span>
          <span className="inline-flex h-9 min-w-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg bg-nx-ink/5 px-2 font-medium"><MapPinned aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />{s.maps}</span>
        </div>
      </div>
    </div>
  );
}

// ── The page ──────────────────────────────────────────────────────────────────────────────────────────────────────
const BACK = { light: { desktop: backDesktopLight, phone: backPhoneLight }, dark: { desktop: backDesktopDark, phone: backPhoneDark } };

function Label({ children }: { children: ReactNode }) {
  return <p className="text-caption font-medium nx-muted">{children}</p>;
}

/** A state on a crop of the real map, around where the card opens (the screenshot at 1280 × 800, the card at 690, 341). */
function StateTile({ theme, label, children }: { theme: Theme; label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <Label>{label}</Label>
      <div className="relative h-[27rem] overflow-hidden rounded-2xl ring-1 ring-nx-ink/10"
        style={{ backgroundImage: `url(${BACK[theme].desktop})`, backgroundPosition: "-650px -300px", backgroundSize: "1280px 800px" }}>
        <div className="absolute left-5 top-10">{children}</div>
      </div>
    </div>
  );
}

function ThemeSection({ theme, lang }: { theme: Theme; lang: Lang }) {
  const picked: Form = { chips: ["stories", "condo"], stories: "20", area: null, note: lang === "es" ? "Es una torre de 20 pisos, no de 2." : "It's a 20-story tower, not 2." };
  return (
    <section className="ui-next flex min-w-0 flex-col gap-6 bg-nx-page p-4 text-nx-ink sm:rounded-3xl sm:p-6 sm:ring-1 sm:ring-nx-ink/10" data-theme={theme} data-testid={`panel-${theme}`}>
      <h2 className="text-body font-semibold">{theme === "light" ? "Light" : "Dark"}</h2>
      <div className="flex flex-wrap items-start gap-6">
        <div className="flex min-w-0 flex-1 basis-[40rem] flex-col gap-2" data-testid={`desktop-${theme}`}>
          <Label>1 · Desktop, on the real Discovery map. Click the pencil beside the ×.</Label>
          <div className="relative aspect-[16/10] w-full max-w-[1280px] overflow-hidden rounded-2xl ring-1 ring-nx-ink/10">
            <img src={BACK[theme].desktop} alt="" className="absolute inset-0 h-full w-full object-cover object-left-top" />
            <div className="absolute" style={{ left: "53.9%", top: "42.6%" }}><MockLotCard lang={lang} mode="card" interactive /></div>
          </div>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto" data-testid={`phone-${theme}`}>
          <Label>2 · Phone, 360 px</Label>
          <div className="relative -mx-4 h-[760px] w-[calc(100%+2rem)] overflow-hidden sm:mx-0 sm:w-[360px] sm:rounded-[2rem] sm:ring-1 sm:ring-nx-ink/15">
            <img src={BACK[theme].phone} alt="" className="absolute inset-0 h-full w-full object-cover object-left-top" />
            <div className="absolute left-1/2 top-[200px] -translate-x-1/2"><MockLotCard lang={lang} mode="form" interactive initial={{ ...EMPTY, chips: ["stories"], stories: "4" }} /></div>
          </div>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <Label>3 · The states</Label>
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(min(20rem,100%),1fr))]">
          <StateTile theme={theme} label="a · The card: one pencil, its name on hover"><MockLotCard lang={lang} mode="card" showTip /></StateTile>
          <StateTile theme={theme} label="b · Opened: tap what's wrong"><MockLotCard lang={lang} mode="form" /></StateTile>
          <StateTile theme={theme} label="c · Two picked, 20 typed, a note"><MockLotCard lang={lang} mode="form" initial={picked} /></StateTile>
          <StateTile theme={theme} label="d · Sent (goes back to the card by itself)"><MockLotCard lang={lang} mode="sent" /></StateTile>
          <StateTile theme={theme} label="e · Back on the card: the pencil is a check"><MockLotCard lang={lang} mode="afterSend" showTip /></StateTile>
          <StateTile theme={theme} label="f · After review: an icon says whose figure it is"><MockLotCard lang={lang} mode="reviewed" showTip /></StateTile>
        </div>
      </div>
    </section>
  );
}

export default function SuggestCorrectionMockup() {
  const { i18n } = useTranslation();
  const [lang, setLang] = useState<Lang>(i18n.language.startsWith("es") ? "es" : "en");
  useEffect(() => { void i18n.changeLanguage(lang); }, [lang, i18n]);
  // The site's theme sits on <html>; a dark one would cascade into the light section, so the page pins it light while
  // it is open (each section sets its own).
  useEffect(() => {
    const root = document.documentElement, was = root.getAttribute("data-theme");
    root.setAttribute("data-theme", "light");
    return () => { if (was) root.setAttribute("data-theme", was); };
  }, []);
  const chip = (on: boolean) => `rounded-full px-3.5 py-1.5 text-caption touch-target ${on ? "bg-nx-primary font-semibold text-nx-primary-fg" : "hover:bg-nx-ink/5"}`;
  return (
    <main className="ui-next min-h-screen bg-nx-page py-4 text-nx-ink sm:p-8" data-theme="light">
      <div className="mx-auto flex max-w-[110rem] flex-col gap-6">
        <header className="flex flex-wrap items-center justify-between gap-3 px-4 sm:px-0">
          <div>
            <h1 className="text-[1.375rem] font-semibold">Suggest a correction · mockup 2</h1>
            <p className="text-caption nx-muted">Dev-only (decision Item 129). The real card over screenshots of the real map. Nothing is sent.</p>
          </div>
          <div className="inline-flex rounded-full bg-nx-block p-1" role="group" aria-label="Language">
            <button type="button" className={chip(lang === "en")} aria-pressed={lang === "en"} onClick={() => setLang("en")}>English</button>
            <button type="button" className={chip(lang === "es")} aria-pressed={lang === "es"} onClick={() => setLang("es")}>Español (MX)</button>
          </div>
        </header>
        <ThemeSection theme="light" lang={lang} />
        <ThemeSection theme="dark" lang={lang} />
      </div>
    </main>
  );
}
