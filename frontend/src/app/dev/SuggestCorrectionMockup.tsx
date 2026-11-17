// DEV-ONLY MOCKUP (decision Item 129): how a signed-in user suggests a correction to a lot's estimated facts from the
// Discovery map's lot card. Not production code: the route exists only under `import.meta.env.DEV` (main.tsx), so the
// production build tree-shakes this file away. The strings live here, not in the catalogs, until the build PRs land.
// Built from the real pieces: the SnowUI tokens (app.css), the map lot card's frame (ExploreMap.tsx `LotCard`),
// `Pill`, Lucide icons at `STROKE`, the main-button classes the Settings page uses.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  ArrowRight, Building, Building2, Check, CircleCheck, EqualApproximately, Layers, LogIn, MessageSquarePlus, MessageCircle,
  Minus, Plus, Ruler, SquareArrowOutUpRight, SquareDashed, UserCheck, X, type LucideIcon,
} from "lucide-react";
import { STROKE } from "../icons";
import { Pill } from "../ui/Blocks";

type Lang = "en" | "es";
type Theme = "light" | "dark";

// es-MX, usted register (memory: Spanish = Mexican).
const S = {
  en: {
    link: "Suggest a correction",
    sentLink: "Correction sent, in review",
    q: "What's wrong with this building?",
    hint: "Pick all that apply.",
    stories: "Wrong number of stories",
    storiesHas: "It has", storiesUnit: (n: number) => (n === 1 ? "story" : "stories"), storiesWe: (n: number) => `We used ${n}`,
    fewer: "Fewer stories", more: "More stories",
    area: "Floor area looks wrong", areaHigh: "Too high", areaLow: "Too low",
    gone: "The building is gone, the lot is empty",
    there: "There is a building here",
    notCondo: "It's not a condo", isCondo: "It is a condo",
    other: "Something else",
    note: "Add a note", optional: "optional",
    placeholder: "For example: a fourth floor was added in 2019",
    send: "Send", cancel: "Cancel",
    thanks: "Thanks, we'll review it",
    thanksSub: "Nothing on the card changes until it's checked against City and County records.",
    done: "Done",
    signTitle: "Sign in to suggest a correction",
    signSub: "It's free. Your report stays private.",
    signIn: "Sign in",
    reviewed: "Reviewed user report",
    floors: (n: number) => `${n} stories`,
  },
  es: {
    link: "Sugerir una corrección",
    sentLink: "Corrección enviada, en revisión",
    q: "¿Qué está mal con este edificio?",
    hint: "Elija todas las que apliquen.",
    stories: "Número de pisos incorrecto",
    storiesHas: "Tiene", storiesUnit: (n: number) => (n === 1 ? "piso" : "pisos"), storiesWe: (n: number) => `Usamos ${n}`,
    fewer: "Menos pisos", more: "Más pisos",
    area: "La superficie construida parece incorrecta", areaHigh: "Muy alta", areaLow: "Muy baja",
    gone: "Ya no hay edificio, el terreno está vacío",
    there: "Aquí hay un edificio",
    notCondo: "No es un condominio", isCondo: "Es un condominio",
    other: "Otra cosa",
    note: "Agregue una nota", optional: "opcional",
    placeholder: "Por ejemplo: en 2019 le agregaron un cuarto piso",
    send: "Enviar", cancel: "Cancelar",
    thanks: "Gracias, lo revisaremos",
    thanksSub: "Nada cambia en la tarjeta hasta que lo comparemos con los registros de la Ciudad y del Condado.",
    done: "Listo",
    signTitle: "Inicie sesión para sugerir una corrección",
    signSub: "Es gratis. Su reporte es privado.",
    signIn: "Iniciar sesión",
    reviewed: "Reporte de usuario revisado",
    floors: (n: number) => `${n} pisos`,
  },
} as const;
type Strings = (typeof S)[Lang];

// A sample lot (made up for the mockup): a two-flat-sized condo building whose floor area is an estimate.
const LOT = { title: "2034 W Le Moyne St", zone: "RS-3", lotSqft: 3125, roomSqft: 1240, stories: 2, condo: true, hasBuilding: true };

const NOTE_MAX = 280;
const BTN_PRIMARY = "inline-flex items-center justify-center gap-2 rounded-full bg-nx-primary px-4 py-2 font-semibold text-nx-primary-fg disabled:opacity-40 touch-target";
const BTN_QUIET = "inline-flex items-center justify-center gap-2 rounded-full px-4 py-2 font-medium hover:bg-nx-ink/5 touch-target";

type Pick = "stories" | "area" | "gone" | "there" | "condo" | "other";
export type FormState = { picks: Pick[]; stories: number; area: "high" | "low" | null; note: string };
const EMPTY: FormState = { picks: [], stories: LOT.stories, area: null, note: "" };

// ── The option row: a toggle button (aria-pressed), the word always visible, a check when picked ──────────────────
function Option({ icon: Icon, label, on, onToggle, children }: { icon: LucideIcon; label: string; on: boolean; onToggle: () => void; children?: ReactNode }) {
  return (
    <li className={`overflow-hidden rounded-xl ${on ? "bg-nx-ink/[0.07] ring-1 ring-nx-ink/70" : "bg-nx-block"}`}>
      <button type="button" aria-pressed={on} onClick={onToggle}
        className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-caption hover:bg-nx-ink/5 touch-target">
        <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-md ${on ? "bg-nx-ink text-nx-on-ink" : "nx-muted"}`}>
          {on ? <Check aria-hidden className="h-3.5 w-3.5" strokeWidth={2.25} /> : <Icon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />}
        </span>
        <span className={on ? "font-medium" : ""}>{label}</span>
      </button>
      {on && children && <div className="px-3 pb-3 pl-[2.625rem]">{children}</div>}
    </li>
  );
}

function Stepper({ s, value, onChange }: { s: Strings; value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption">
      <span>{s.storiesHas}</span>
      <span className="inline-flex items-center rounded-full bg-nx-page ring-1 ring-nx-ink/15">
        <button type="button" aria-label={s.fewer} disabled={value <= 1} onClick={() => onChange(value - 1)}
          className="grid h-8 w-8 place-items-center rounded-full hover:bg-nx-ink/5 disabled:opacity-30 touch-icon">
          <Minus aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
        </button>
        <span className="min-w-[1.75rem] text-center text-body font-semibold tabular-nums" aria-live="polite">{value}</span>
        <button type="button" aria-label={s.more} disabled={value >= 40} onClick={() => onChange(value + 1)}
          className="grid h-8 w-8 place-items-center rounded-full hover:bg-nx-ink/5 disabled:opacity-30 touch-icon">
          <Plus aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
        </button>
      </span>
      <span>{s.storiesUnit(value)}</span>
      <span className="nx-muted">({s.storiesWe(LOT.stories)})</span>
    </div>
  );
}

function Segmented({ value, options, onChange }: { value: string | null; options: Array<[string, string]>; onChange: (v: "high" | "low") => void }) {
  return (
    <div className="inline-flex rounded-full bg-nx-page p-0.5 text-caption ring-1 ring-nx-ink/15">
      {options.map(([k, label]) => (
        <button key={k} type="button" aria-pressed={value === k} onClick={() => onChange(k as "high" | "low")}
          className={`rounded-full px-3 py-1 ${value === k ? "bg-nx-ink font-medium text-nx-on-ink" : "hover:bg-nx-ink/5"}`}>{label}</button>
      ))}
    </div>
  );
}

// ── The form ──────────────────────────────────────────────────────────────────────────────────────────────────────
export function SuggestForm({ lang, signedIn = true, initial = EMPTY, sentInitially = false, onClose }: {
  lang: Lang; signedIn?: boolean; initial?: FormState; sentInitially?: boolean; onClose?: () => void;
}) {
  const s = S[lang];
  const [f, setF] = useState<FormState>(initial);
  const [sent, setSent] = useState(sentInitially);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const has = (p: Pick) => f.picks.includes(p);
  const toggle = (p: Pick) => setF((x) => {
    let picks = x.picks.includes(p) ? x.picks.filter((q) => q !== p) : [...x.picks, p];
    // "Gone" makes the size questions moot: picking it clears them (and they hide).
    if (p === "gone" && picks.includes("gone")) picks = picks.filter((q) => q !== "stories" && q !== "area");
    return { ...x, picks };
  });
  useEffect(() => { if (has("other")) noteRef.current?.focus(); }, [f.picks]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!signedIn) {
    return (
      <div className="flex flex-col gap-3">
        <Head s={s} onClose={onClose} />
        <div className="flex flex-col gap-1 rounded-xl bg-nx-block p-3">
          <p className="text-caption font-medium">{s.signTitle}</p>
          <p className="text-caption nx-muted">{s.signSub}</p>
        </div>
        <div className="flex justify-end gap-1">
          <button type="button" className={BTN_QUIET} onClick={onClose}>{s.cancel}</button>
          <button type="button" className={BTN_PRIMARY}><LogIn aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{s.signIn}</button>
        </div>
      </div>
    );
  }

  if (sent) {
    return (
      <div className="flex flex-col gap-3" role="status">
        <div className="flex items-start gap-2.5 pr-6">
          <CircleCheck aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-nx-pill-green" strokeWidth={STROKE} />
          <div className="flex flex-col gap-1">
            <p className="text-body font-semibold">{s.thanks}</p>
            <p className="text-caption nx-muted">{s.thanksSub}</p>
          </div>
        </div>
        <div className="flex justify-end">
          <button type="button" className={BTN_QUIET} onClick={() => { setSent(false); setF(EMPTY); onClose?.(); }}>{s.done}</button>
        </div>
      </div>
    );
  }

  return (
    <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); setSent(true); }}>
      <Head s={s} onClose={onClose} />
      <fieldset className="flex flex-col gap-1.5">
        <legend className="sr-only">{s.q}</legend>
        <ul className="flex flex-col gap-1.5">
          {LOT.hasBuilding && !has("gone") && (
            <Option icon={Layers} label={s.stories} on={has("stories")} onToggle={() => toggle("stories")}>
              <Stepper s={s} value={f.stories} onChange={(v) => setF((x) => ({ ...x, stories: v }))} />
            </Option>
          )}
          {LOT.hasBuilding && !has("gone") && (
            <Option icon={Ruler} label={s.area} on={has("area")} onToggle={() => toggle("area")}>
              <Segmented value={f.area} options={[["high", s.areaHigh], ["low", s.areaLow]]} onChange={(v) => setF((x) => ({ ...x, area: v }))} />
            </Option>
          )}
          {LOT.hasBuilding
            ? <Option icon={SquareDashed} label={s.gone} on={has("gone")} onToggle={() => toggle("gone")} />
            : <Option icon={Building2} label={s.there} on={has("there")} onToggle={() => toggle("there")} />}
          <Option icon={Building} label={LOT.condo ? s.notCondo : s.isCondo} on={has("condo")} onToggle={() => toggle("condo")} />
          <Option icon={MessageCircle} label={s.other} on={has("other")} onToggle={() => toggle("other")} />
        </ul>
      </fieldset>
      <label className="flex flex-col gap-1 text-caption">
        <span>{s.note} <span className="nx-muted">({s.optional})</span></span>
        <textarea ref={noteRef} rows={2} maxLength={NOTE_MAX} value={f.note} placeholder={s.placeholder}
          onChange={(e) => setF((x) => ({ ...x, note: e.target.value }))}
          className="resize-none rounded-xl bg-nx-block px-3 py-2 text-caption text-nx-ink placeholder:text-nx-ink/45 focus:outline-none focus:ring-1 focus:ring-nx-ink/60" />
        {f.note.length > NOTE_MAX - 60 && <span className="self-end nx-muted tabular-nums">{f.note.length}/{NOTE_MAX}</span>}
      </label>
      <div className="flex justify-end gap-1">
        <button type="button" className={BTN_QUIET} onClick={onClose}>{s.cancel}</button>
        <button type="submit" className={BTN_PRIMARY} disabled={f.picks.length === 0}>{s.send}</button>
      </div>
    </form>
  );
}

function Head({ s, onClose }: { s: Strings; onClose?: () => void }) {
  return (
    <div className="flex items-start justify-between gap-2">
      <div className="flex flex-col">
        <p className="text-body font-semibold">{s.q}</p>
        <p className="text-caption nx-muted">{LOT.title} · {s.hint}</p>
      </div>
      {onClose && (
        <button type="button" onClick={onClose} aria-label="Close" className="-mr-2 -mt-2 grid h-7 w-7 shrink-0 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon">
          <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
        </button>
      )}
    </div>
  );
}

// ── The map lot card (ExploreMap.tsx `LotCard`), with the estimate line and the new link ─────────────────────────
type CardMode = "card" | "form" | "sent" | "signedOut" | "reviewed";

function MapLotCard({ lang, mode: initialMode, signedIn = true, interactive = false }: { lang: Lang; mode: CardMode; signedIn?: boolean; interactive?: boolean }) {
  const { t } = useTranslation("next");
  const s = S[lang];
  const [mode, setMode] = useState<CardMode>(initialMode);
  const [sentOnce, setSentOnce] = useState(initialMode === "sent");
  const n = (v: number) => v.toLocaleString(lang === "es" ? "es-MX" : "en-US");
  const open = mode === "form" || mode === "signedOut" || mode === "sent";
  return (
    <div role="dialog" aria-label={LOT.title}
      className={`relative rounded-2xl bg-nx-page p-4 text-caption text-nx-ink shadow-[0_8px_32px_rgb(0_0_0/0.18)] ${open ? "w-[20rem] max-w-full" : "w-[17.5rem] max-w-full"}`}>
      {open ? (
        <SuggestForm key={mode} lang={lang} signedIn={mode !== "signedOut" && signedIn} sentInitially={mode === "sent"}
          onClose={interactive ? () => { if (mode === "form") setSentOnce(true); setMode("card"); } : undefined} />
      ) : (
        <>
          <button type="button" aria-label={t("discovery.map.close")} className="absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon">
            <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
          </button>
          <div className="flex flex-col gap-1.5 pr-6">
            <p className="text-body font-semibold">{LOT.title}</p>
            <p className="nx-muted">{[LOT.zone, t("discovery.card.lotValue", { value: n(LOT.lotSqft) })].join(" · ")}</p>
            <p>{t("discovery.card.roomValue", { value: n(mode === "reviewed" ? 610 : LOT.roomSqft) })}</p>
            {mode === "reviewed" ? (
              <span className="flex flex-wrap items-center gap-1.5">
                <Pill tone="gray" icon={UserCheck}>{s.reviewed}</Pill>
                <span className="nx-muted">{s.floors(3)}</span>
              </span>
            ) : (
              <span className="flex items-start gap-1 text-[11px] nx-muted">
                <EqualApproximately aria-hidden className="mt-px h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} />
                {t("discovery.card.basis.footprint")}
              </span>
            )}
            <button type="button" className="mt-1 inline-flex items-center gap-1 self-start font-medium underline underline-offset-2">
              {t("discovery.card.open")}<ArrowRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
            </button>
            <span className="inline-flex items-center gap-1 nx-muted underline underline-offset-2">
              {t("map.streetView.link")}<SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
            </span>
            {mode !== "reviewed" && (sentOnce && mode === "card" ? (
              <span className="mt-1 inline-flex items-center gap-1 border-t border-nx-ink/10 pt-2 nx-muted">
                <CircleCheck aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{s.sentLink}
              </span>
            ) : (
              <button type="button" onClick={() => interactive && setMode(signedIn ? "form" : "signedOut")}
                className="mt-1 inline-flex items-center gap-1 self-stretch border-t border-nx-ink/10 pt-2 nx-muted hover:text-nx-ink">
                <MessageSquarePlus aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
                <span className="underline underline-offset-2">{s.link}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ── A stand-in for the map behind the card: blocks, streets, this lot outlined in "this lot" ink ───────────────
function MapBackdrop({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-2xl bg-nx-block ${className}`}>
      <svg aria-hidden className="absolute inset-0 h-full w-full" preserveAspectRatio="xMidYMid slice" viewBox="0 0 720 480">
        <rect width="720" height="480" fill="rgb(var(--nx-block))" />
        {[0, 1, 2, 3].map((r) => [0, 1, 2, 3, 4].map((c) => (
          <rect key={`${r}-${c}`} x={20 + c * 145} y={14 + r * 120} width="125" height="100" rx="3"
            fill={c === 1 && r === 1 ? "rgb(var(--nx-chart-1) / 0.28)" : "rgb(var(--nx-ink) / 0.06)"} />
        )))}
        {[0, 1, 2, 3, 4, 5].map((i) => <line key={i} x1={185} y1={134 + i * 16.6} x2={290} y2={134 + i * 16.6} stroke="rgb(var(--nx-page))" strokeWidth="1.5" />)}
        <rect x="185" y="167" width="105" height="16.6" fill="none" stroke="rgb(var(--nx-lot-edge))" strokeWidth="4" />
        <rect x="185" y="167" width="105" height="16.6" fill="rgb(var(--nx-lot) / 0.2)" stroke="rgb(var(--nx-lot))" strokeWidth="2" />
      </svg>
      {children}
    </div>
  );
}

// ── The page ──────────────────────────────────────────────────────────────────────────────────────────────────────
function Label({ children }: { children: ReactNode }) {
  return <p className="text-caption font-medium nx-muted">{children}</p>;
}

function ThemePanel({ theme, lang }: { theme: Theme; lang: Lang }) {
  const s = S[lang];
  const picked: FormState = { picks: ["stories", "condo"], stories: 3, area: null, note: lang === "es" ? "En 2019 le agregaron un cuarto piso atrás." : "A third floor was added in 2019." };
  return (
    <section className="ui-next flex min-w-0 flex-col gap-6 bg-nx-page p-4 text-nx-ink sm:rounded-3xl sm:p-6 sm:ring-1 sm:ring-nx-ink/10" data-theme={theme} data-testid={`panel-${theme}`}>
      <h2 className="text-body font-semibold">{theme === "light" ? "Light" : "Dark"}</h2>

      <div className="flex flex-col gap-2" data-testid={`desktop-${theme}`}>
        <Label>1 · Desktop: the map card opens the form in place (interactive: tap the link)</Label>
        <MapBackdrop className="h-[34rem]">
          <div className="absolute left-2 right-2 top-[6%] sm:left-[30%] sm:right-auto"><MapLotCard lang={lang} mode="card" interactive /></div>
        </MapBackdrop>
      </div>

      <div className="flex flex-col gap-2">
        <Label>2 · The states</Label>
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(min(20rem,100%),1fr))]">
          <div className="flex flex-col gap-2"><Label>a · Card with the link</Label><MapLotCard lang={lang} mode="card" /></div>
          <div className="flex flex-col gap-2"><Label>b · Two picked, stories stepped to 3, a note</Label>
            <div className="w-[20rem] max-w-full rounded-2xl bg-nx-page p-4 text-caption shadow-[0_8px_32px_rgb(0_0_0/0.18)]"><SuggestForm lang={lang} initial={picked} /></div>
          </div>
          <div className="flex flex-col gap-2"><Label>c · Sent</Label><MapLotCard lang={lang} mode="sent" /></div>
          <div className="flex flex-col gap-2"><Label>d · Signed out: a sign-in prompt, nothing hidden</Label><MapLotCard lang={lang} mode="signedOut" signedIn={false} /></div>
          <div className="flex flex-col gap-2"><Label>e · Later, after review: the figure says whose it is</Label><MapLotCard lang={lang} mode="reviewed" /></div>
        </div>
      </div>

      <div className="flex flex-col gap-2" data-testid={`phone-${theme}`}>
        <Label>3 · Phone, 360 px: the same form as a bottom sheet over the map</Label>
        <div className="-mx-4 w-[calc(100%+2rem)] overflow-hidden sm:mx-0 sm:w-[360px] sm:rounded-[2rem] sm:ring-1 sm:ring-nx-ink/15">
          <MapBackdrop className="h-[46rem] rounded-none">
            <div className="absolute inset-x-0 bottom-0 max-h-[85%] overflow-y-auto rounded-t-3xl bg-nx-page px-4 pb-6 pt-2 text-caption shadow-[0_-8px_32px_rgb(0_0_0/0.18)]">
              <div aria-hidden className="mx-auto mb-3 h-1 w-10 rounded-full bg-nx-ink/20" />
              <SuggestForm lang={lang} initial={{ ...EMPTY, picks: ["stories"], stories: 3 }} onClose={() => {}} />
            </div>
          </MapBackdrop>
        </div>
        <p className="sr-only">{s.q}</p>
      </div>
    </section>
  );
}

export default function SuggestCorrectionMockup() {
  const { i18n } = useTranslation();
  const [lang, setLang] = useState<Lang>(i18n.language.startsWith("es") ? "es" : "en");
  useEffect(() => { void i18n.changeLanguage(lang); }, [lang, i18n]);
  // The site's theme sits on <html>; a dark one would cascade into the light panel, so the mockup page pins it light
  // while it is open (each panel then sets its own theme).
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
            <h1 className="text-[1.375rem] font-semibold">Suggest a correction · mockup</h1>
            <p className="text-caption nx-muted">Dev-only (decision Item 129). Sample lot, nothing is sent.</p>
          </div>
          <div className="inline-flex rounded-full bg-nx-block p-1" role="group" aria-label="Language">
            <button type="button" className={chip(lang === "en")} aria-pressed={lang === "en"} onClick={() => setLang("en")}>English</button>
            <button type="button" className={chip(lang === "es")} aria-pressed={lang === "es"} onClick={() => setLang("es")}>Español (MX)</button>
          </div>
        </header>
        <div className="grid gap-6 xl:grid-cols-2">
          <ThemePanel theme="light" lang={lang} />
          <ThemePanel theme="dark" lang={lang} />
        </div>
      </div>
    </main>
  );
}
