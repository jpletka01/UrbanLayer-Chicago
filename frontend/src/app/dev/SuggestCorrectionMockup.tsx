// DEV-ONLY MOCKUP (decision Item 129, third pass after the owner's reviews of 2026-11-17): how anyone suggests a
// correction to a lot's building facts from the Discovery map's lot card. Not production code: the route exists only
// under `import.meta.env.DEV` (`DEV_PAGES` in pages.ts), so the production build drops this file and its images.
// Built on the real card as it is on #242's branch (ExploreMap.tsx `LotCard`), over screenshots of the real Discovery
// map (`mock/*.jpg`, from the local stack). The form takes the focus the way the app's other dialogs do (Settings'
// Delete account, Discovery's filter groups: a dimmed page, a centered dialog on a laptop, a sheet from the bottom on a
// phone), and "sent" is a toast in the page's corner. The build uses Radix Dialog; here the pieces are drawn inside
// each frame (absolute, not fixed) so light and dark, desktop and phone sit side by side. Strings live here until the
// build PRs move them into the `next` catalogs.
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRight, Check, CircleCheck, MapPinned, PencilLine, PersonStanding, UserCheck, X } from "lucide-react";
import { STROKE } from "../icons";
import backDesktopLight from "./mock/back-desktop-light.jpg";
import backDesktopDark from "./mock/back-desktop-dark.jpg";
import backPhoneLight from "./mock/back-phone-light.jpg";
import backPhoneDark from "./mock/back-phone-dark.jpg";

type Lang = "en" | "es";
type Theme = "light" | "dark";
type Device = "desktop" | "phone";

// es-MX, usted register.
const S = {
  en: {
    suggest: "Suggest a correction", sentTip: "Correction sent, in review",
    q: "What's wrong with this building?", close: "Close", cancel: "Cancel",
    chips: { stories: "Stories", area: "Floor area", gone: "No building now", there: "There's a building", condo: "Not a condo", isCondo: "It's a condo", other: "Other" },
    storiesUnit: "stories", storiesLabel: "Number of stories", areaHigh: "Too high", areaLow: "Too low",
    note: "Add a note (optional)", send: "Send", thanks: "Thanks, we'll review it.",
    reviewedTip: "Floor area from a reviewed user report (3 stories)",
    open: "Open profile", streetView: "Street View", maps: "Google Maps",
    lot: "4,800 sq ft lot", room: (v: string) => `Room to build: ${v} sq ft`,
  },
  es: {
    suggest: "Sugerir una corrección", sentTip: "Corrección enviada, en revisión",
    q: "¿Qué está mal con este edificio?", close: "Cerrar", cancel: "Cancelar",
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
type CardMode = "card" | "afterSend" | "reviewed";

const ICON_BTN = "grid h-7 w-7 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon";
const CARD = "w-[17.5rem] max-w-full rounded-2xl bg-nx-page p-4 text-caption text-nx-ink shadow-[0_8px_32px_rgb(0_0_0/0.18)]";
// The app's dialog buttons (Settings): rounded-full, the main one in the primary token (black in light, lavender in dark).
const BTN_PRIMARY = "inline-flex items-center justify-center gap-2 rounded-full bg-nx-primary px-5 py-2 font-semibold text-nx-primary-fg disabled:opacity-40 touch-target";
const BTN_SECONDARY = "inline-flex items-center justify-center gap-2 rounded-full px-4 py-2 font-medium ring-1 ring-nx-ink/15 hover:bg-nx-ink/5 touch-target";

/** An icon button with its name as a tooltip on hover and focus (never hover-only: the click is the action). */
function IconTool({ label, onClick, children, showTip = false }: { label: string; onClick?: () => void; children: ReactNode; showTip?: boolean }) {
  return (
    <span className="group relative">
      <button type="button" aria-label={label} onClick={onClick} className={ICON_BTN}>{children}</button>
      <span role="tooltip" className={`pointer-events-none absolute right-0 top-full z-20 mt-1 whitespace-nowrap rounded-md bg-nx-ink px-2 py-1 text-[11px] text-nx-on-ink ${showTip ? "block" : "hidden group-hover:block group-focus-within:block"}`}>{label}</span>
    </span>
  );
}

// ── The form's body, shared by the dialog and the sheet ───────────────────────────────────────────────────────────
function useForm(initial: Form) {
  const [f, setF] = useState<Form>(initial);
  const on = (c: Chip) => f.chips.includes(c);
  const toggle = (c: Chip) => setF((x) => {
    let chips = x.chips.includes(c) ? x.chips.filter((y) => y !== c) : [...x.chips, c];
    if (c === "gone" && chips.includes("gone")) chips = chips.filter((y) => y !== "stories" && y !== "area"); // moot
    if ((c === "stories" || c === "area") && chips.includes(c)) chips = chips.filter((y) => y !== "gone");
    return { ...x, chips };
  });
  const ready = f.chips.length > 0 && (!on("stories") || /^\d{1,3}$/.test(f.stories)) && (!on("area") || f.area != null);
  return { f, setF, on, toggle, ready };
}

function FormBody({ s, form, big }: { s: Strings; form: ReturnType<typeof useForm>; big: boolean }) {
  const { f, setF, on, toggle } = form;
  const storiesRef = useRef<HTMLInputElement>(null);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const last = f.chips[f.chips.length - 1];
  useEffect(() => {
    if (last === "stories") storiesRef.current?.focus({ preventScroll: true });
    if (last === "other") noteRef.current?.focus({ preventScroll: true });
  }, [last]);
  const chips: Array<[Chip, string]> = [
    ...(LOT.hasBuilding ? [["stories", s.chips.stories], ["area", s.chips.area], ["gone", s.chips.gone]] as Array<[Chip, string]> : [["gone", s.chips.there]] as Array<[Chip, string]>),
    ["condo", LOT.condo ? s.chips.condo : s.chips.isCondo],
    ["other", s.chips.other],
  ];
  const chipH = big ? "h-10 px-4" : "h-9 px-3.5";
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-2" role="group" aria-label={s.q}>
        {chips.map(([c, label]) => (
          <button key={c} type="button" aria-pressed={on(c)} onClick={() => toggle(c)}
            className={`inline-flex items-center gap-1.5 rounded-full text-body touch-target ${chipH} ${on(c) ? "bg-nx-ink font-medium text-nx-on-ink" : "bg-nx-ink/5 hover:bg-nx-ink/10"}`}>
            {on(c) && <Check aria-hidden className="h-4 w-4" strokeWidth={2.25} />}{label}
          </button>
        ))}
      </div>
      {(on("stories") || on("area")) && (
        <div className="flex flex-col gap-3 rounded-2xl bg-nx-block p-3">
          {on("stories") && (
            <label className="flex items-center gap-2.5 text-body">
              <input ref={storiesRef} type="text" inputMode="numeric" pattern="[0-9]*" maxLength={3} aria-label={s.storiesLabel}
                value={f.stories} placeholder={String(LOT.stories)} onFocus={(e) => e.currentTarget.select()}
                onChange={(e) => setF((x) => ({ ...x, stories: e.target.value.replace(/\D/g, "") }))}
                className="h-10 w-16 rounded-xl bg-nx-page text-center text-[1.0625rem] font-semibold tabular-nums text-nx-ink ring-1 ring-nx-ink/15 placeholder:font-normal placeholder:text-nx-ink/40 focus:outline-none focus:ring-nx-ink/60" />
              <span>{s.storiesUnit}</span>
            </label>
          )}
          {on("area") && (
            <div className="grid max-w-[18rem] grid-cols-2 gap-1 rounded-full bg-nx-page p-1 text-body ring-1 ring-nx-ink/15">
              {([["high", s.areaHigh], ["low", s.areaLow]] as const).map(([k, label]) => (
                <button key={k} type="button" aria-pressed={f.area === k} onClick={() => setF((x) => ({ ...x, area: k }))}
                  className={`h-8 rounded-full ${f.area === k ? "bg-nx-ink font-medium text-nx-on-ink" : "hover:bg-nx-ink/5"}`}>{label}</button>
              ))}
            </div>
          )}
        </div>
      )}
      <textarea ref={noteRef} rows={3} maxLength={280} value={f.note} placeholder={s.note} aria-label={s.note}
        onChange={(e) => setF((x) => ({ ...x, note: e.target.value }))}
        className="resize-none rounded-2xl bg-nx-block px-4 py-3 text-body text-nx-ink placeholder:text-nx-ink/50 focus:outline-none focus:ring-1 focus:ring-nx-ink/60" />
    </div>
  );
}

function Title({ s }: { s: Strings }) {
  return (
    <div className="flex flex-col gap-0.5 pr-10">
      <h2 className="text-[1.0625rem] font-semibold leading-snug">{s.q}</h2>
      <p className="text-caption nx-muted">{LOT.title}</p>
    </div>
  );
}

// ── Desktop: a centered dialog over the dimmed page (Settings' dialog, a little wider) ─────────────────────────────
function DesktopDialog({ s, initial = EMPTY, onClose, onSend }: { s: Strings; initial?: Form; onClose?: () => void; onSend?: () => void }) {
  const form = useForm(initial);
  return (
    <div className="absolute inset-0 z-30 grid place-items-center bg-black/30 p-4" onClick={onClose}>
      <form role="dialog" aria-modal="true" aria-label={s.q} onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => { e.preventDefault(); if (form.ready) onSend?.(); }}
        className="relative flex w-[min(32rem,100%)] flex-col gap-5 rounded-3xl bg-nx-page p-6 text-nx-ink shadow-[0_8px_32px_rgb(0_0_0/0.25)]">
        <span className="absolute right-4 top-4"><IconTool label={s.close} onClick={onClose}><X aria-hidden className="h-5 w-5" strokeWidth={STROKE} /></IconTool></span>
        <Title s={s} />
        <FormBody s={s} form={form} big={false} />
        <div className="flex justify-end gap-2">
          <button type="button" className={BTN_SECONDARY} onClick={onClose}>{s.cancel}</button>
          <button type="submit" className={BTN_PRIMARY} disabled={!form.ready}>{s.send}</button>
        </div>
      </form>
    </div>
  );
}

// ── Phone: a sheet that slides up over the whole screen; drag the handle down (or ×) to close ─────────────────────
function PhoneSheet({ s, initial = EMPTY, onClose, onSend }: { s: Strings; initial?: Form; onClose?: () => void; onSend?: () => void }) {
  const form = useForm(initial);
  const [dy, setDy] = useState(0);
  const [dragging, setDragging] = useState(false);
  const start = useRef<number | null>(null);
  const [shown, setShown] = useState(!onClose); // a static state is shown at once; a live one slides in
  useEffect(() => { const id = requestAnimationFrame(() => setShown(true)); return () => cancelAnimationFrame(id); }, []);
  return (
    <div className="absolute inset-0 z-30 bg-black/30" onClick={onClose}>
      <form role="dialog" aria-modal="true" aria-label={s.q} onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => { e.preventDefault(); if (form.ready) onSend?.(); }}
        style={{ transform: `translateY(${shown ? dy : 800}px)`, transition: dragging ? "none" : "transform 250ms ease-out" }}
        className="absolute inset-x-0 bottom-0 top-6 flex flex-col rounded-t-3xl bg-nx-page text-nx-ink shadow-[0_-8px_32px_rgb(0_0_0/0.2)]">
        <div className="flex cursor-grab touch-none justify-center pb-2 pt-3"
          onPointerDown={(e) => { start.current = e.clientY; setDragging(true); e.currentTarget.setPointerCapture(e.pointerId); }}
          onPointerMove={(e) => { if (start.current != null) setDy(Math.max(0, e.clientY - start.current)); }}
          onPointerUp={() => { const far = dy > 120; start.current = null; setDragging(false); setDy(0); if (far) onClose?.(); }}>
          <span aria-hidden className="h-1 w-10 rounded-full bg-nx-ink/20" />
        </div>
        <span className="absolute right-3 top-4"><IconTool label={s.close} onClick={onClose}><X aria-hidden className="h-5 w-5" strokeWidth={STROKE} /></IconTool></span>
        <div className="flex flex-1 flex-col gap-5 overflow-y-auto px-5 pb-4 pt-1">
          <Title s={s} />
          <FormBody s={s} form={form} big />
        </div>
        <div className="border-t border-nx-ink/10 px-5 pb-6 pt-3">
          <button type="submit" disabled={!form.ready} className={`${BTN_PRIMARY} h-12 w-full text-body`}>{s.send}</button>
        </div>
      </form>
    </div>
  );
}

// ── The toast, in the page's corner ───────────────────────────────────────────────────────────────────────────────
function Toast({ s, device, onClose }: { s: Strings; device: Device; onClose?: () => void }) {
  return (
    <div role="status" className={`absolute z-40 flex items-center gap-2.5 rounded-2xl bg-nx-ink py-2.5 pl-4 pr-2 text-body text-nx-on-ink shadow-[0_8px_32px_rgb(0_0_0/0.25)] ${device === "desktop" ? "bottom-5 right-5" : "inset-x-4 top-4"}`}>
      <CircleCheck aria-hidden className="h-5 w-5 shrink-0" strokeWidth={STROKE} />
      <span className="flex-1">{s.thanks}</span>
      <button type="button" aria-label={s.close} onClick={onClose} className="grid h-7 w-7 place-items-center rounded-lg hover:bg-nx-on-ink/10 touch-icon">
        <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
      </button>
    </div>
  );
}

// ── The real map card (#242), with the pencil beside the close button ─────────────────────────────────────────────
function MockLotCard({ lang, mode, onSuggest, showTip = false }: { lang: Lang; mode: CardMode; onSuggest?: () => void; showTip?: boolean }) {
  const s = S[lang];
  const n = (v: number) => v.toLocaleString(lang === "es" ? "es-MX" : "en-US");
  return (
    <div className={`relative ${CARD}`}>
      <div className="absolute right-2 top-2 flex items-center">
        {mode === "afterSend" ? (
          <IconTool label={s.sentTip} showTip={showTip}><Check aria-hidden className="h-4 w-4 nx-muted" strokeWidth={STROKE} /></IconTool>
        ) : mode === "card" ? (
          <IconTool label={s.suggest} showTip={showTip} onClick={onSuggest}><PencilLine aria-hidden className="h-4 w-4 nx-muted" strokeWidth={STROKE} /></IconTool>
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
              <span className="inline-flex" tabIndex={0} aria-label={s.reviewedTip}><UserCheck aria-hidden className="h-3.5 w-3.5 nx-muted" strokeWidth={STROKE} /></span>
              <span role="tooltip" className={`pointer-events-none absolute left-0 top-full z-20 mt-1 w-[13rem] rounded-md bg-nx-ink px-2 py-1 text-[11px] text-nx-on-ink ${showTip ? "block" : "hidden group-hover:block group-focus-within:block"}`}>{s.reviewedTip}</span>
            </>
          )}
        </p>
      </div>
      <div className="mt-3 flex flex-col gap-2">
        <span className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-nx-ink px-3 font-semibold text-nx-on-ink">{s.open}<ArrowRight aria-hidden className="h-4 w-4" strokeWidth={STROKE} /></span>
        <div className="grid grid-cols-2 gap-2">
          <span className="inline-flex h-9 min-w-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg bg-nx-ink/5 px-2 font-medium"><PersonStanding aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />{s.streetView}</span>
          <span className="inline-flex h-9 min-w-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg bg-nx-ink/5 px-2 font-medium"><MapPinned aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />{s.maps}</span>
        </div>
      </div>
    </div>
  );
}

// ── A screen: the real page behind, the card on the lot, and the flow (card → form → toast) ───────────────────────
const BACK = { light: { desktop: backDesktopLight, phone: backPhoneLight }, dark: { desktop: backDesktopDark, phone: backPhoneDark } };
type Step = "card" | "form" | "toast";

function Screen({ theme, device, lang, step: startStep, initial, cardMode, interactive = false, showTip = false, testid }: {
  theme: Theme; device: Device; lang: Lang; step: Step; initial?: Form; cardMode?: CardMode; interactive?: boolean; showTip?: boolean; testid?: string;
}) {
  const s = S[lang];
  const [step, setStep] = useState<Step>(startStep);
  const [sent, setSent] = useState(startStep === "toast");
  useEffect(() => {
    if (interactive && step === "toast") { const id = setTimeout(() => setStep("card"), 4000); return () => clearTimeout(id); }
  }, [interactive, step]);
  const mode: CardMode = cardMode ?? (sent ? "afterSend" : "card");
  const frame = device === "desktop"
    ? "relative aspect-[16/10] w-full max-w-[1280px] overflow-hidden rounded-2xl ring-1 ring-nx-ink/10"
    : "relative -mx-4 h-[760px] w-[calc(100%+2rem)] overflow-hidden sm:mx-0 sm:w-[360px] sm:rounded-[2rem] sm:ring-1 sm:ring-nx-ink/15";
  // The desktop screen is a real 1280 × 800 page (the screenshot's size), scaled to fit, so the card and the dialog keep
  // their true size against the page.
  const outer = useRef<HTMLDivElement>(null);
  const [k, setK] = useState(1);
  useLayoutEffect(() => {
    if (device !== "desktop" || !outer.current) return;
    const el = outer.current;
    const ro = new ResizeObserver(() => setK(el.clientWidth / 1280));
    ro.observe(el);
    return () => ro.disconnect();
  }, [device]);
  const cardAt = device === "desktop" ? { left: 690, top: 341 } : { left: 40, top: 200 };
  const inner = device === "desktop" ? { width: 1280, height: 800, transform: `scale(${k})`, transformOrigin: "0 0" } : { inset: 0 };
  return (
    <div className={frame} data-testid={testid} ref={outer}>
     <div className="absolute" style={inner}>
      <img src={BACK[theme][device]} alt="" className="absolute inset-0 h-full w-full object-cover object-left-top" />
      <div className="absolute" style={cardAt}>
        <MockLotCard lang={lang} mode={mode} showTip={showTip} onSuggest={interactive ? () => setStep("form") : undefined} />
      </div>
      {step === "form" && (device === "desktop"
        ? <DesktopDialog s={s} initial={initial} onClose={interactive ? () => setStep("card") : undefined} onSend={interactive ? () => { setSent(true); setStep("toast"); } : undefined} />
        : <PhoneSheet s={s} initial={initial} onClose={interactive ? () => setStep("card") : undefined} onSend={interactive ? () => { setSent(true); setStep("toast"); } : undefined} />)}
      {step === "toast" && <Toast s={s} device={device} onClose={interactive ? () => setStep("card") : undefined} />}
     </div>
    </div>
  );
}

// ── The page ──────────────────────────────────────────────────────────────────────────────────────────────────────
function Label({ children }: { children: ReactNode }) {
  return <p className="text-caption font-medium nx-muted">{children}</p>;
}

function ThemeSection({ theme, lang }: { theme: Theme; lang: Lang }) {
  const picked: Form = { chips: ["stories", "condo"], stories: "20", area: null, note: lang === "es" ? "Es una torre de 20 pisos, no de 2." : "It's a 20-story tower, not 2." };
  const phonePicked: Form = { ...EMPTY, chips: ["stories"], stories: "4" };
  return (
    <section className="ui-next flex min-w-0 flex-col gap-6 bg-nx-page p-4 text-nx-ink sm:rounded-3xl sm:p-6 sm:ring-1 sm:ring-nx-ink/10" data-theme={theme} data-testid={`panel-${theme}`}>
      <h2 className="text-body font-semibold">{theme === "light" ? "Light" : "Dark"}</h2>
      <div className="flex flex-wrap items-start gap-6">
        <div className="flex min-w-0 flex-1 basis-[40rem] flex-col gap-2" data-testid={`desktop-${theme}`}>
          <Label>1 · Desktop, live: click the pencil beside the card's ×, fill it in, Send.</Label>
          <Screen theme={theme} device="desktop" lang={lang} step="card" interactive testid={`desktop-live-${theme}`} />
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto" data-testid={`phone-${theme}`}>
          <Label>2 · Phone, 360 px, live: tap the pencil; drag the handle down to close.</Label>
          <Screen theme={theme} device="phone" lang={lang} step="card" interactive testid={`phone-live-${theme}`} />
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <Label>3 · Desktop states</Label>
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="flex min-w-0 flex-col gap-2"><Label>a · The card: one pencil, its name on hover</Label><Screen theme={theme} device="desktop" lang={lang} step="card" showTip /></div>
          <div className="flex min-w-0 flex-col gap-2"><Label>b · The form takes the focus: a dialog over the dimmed page</Label><Screen theme={theme} device="desktop" lang={lang} step="form" initial={picked} testid={`desktop-form-${theme}`} /></div>
          <div className="flex min-w-0 flex-col gap-2"><Label>c · Sent: a toast in the corner, the pencil is a check</Label><Screen theme={theme} device="desktop" lang={lang} step="toast" testid={`desktop-toast-${theme}`} /></div>
          <div className="flex min-w-0 flex-col gap-2"><Label>d · After review: an icon says whose figure it is</Label><Screen theme={theme} device="desktop" lang={lang} step="card" cardMode="reviewed" showTip /></div>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <Label>4 · Phone states</Label>
        <div className="flex flex-wrap gap-4">
          <div className="flex w-full flex-col gap-2 sm:w-auto"><Label>a · The sheet, Stories picked</Label><Screen theme={theme} device="phone" lang={lang} step="form" initial={phonePicked} testid={`phone-form-${theme}`} /></div>
          <div className="flex w-full flex-col gap-2 sm:w-auto"><Label>b · Sent: the toast at the top</Label><Screen theme={theme} device="phone" lang={lang} step="toast" testid={`phone-toast-${theme}`} /></div>
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
            <h1 className="text-[1.375rem] font-semibold">Suggest a correction · mockup 3</h1>
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
