// The new landing page (Phase 8, wireframe v5 approved by the owner 2026-11-12): one calm first screen (the menu,
// language, sign in, one line, one picture), an address bar pinned to the bottom of the screen at every scroll
// position, then bands that show the product instead of describing it. Motion, all of it stopped under reduced
// motion: the hero scene drifts, the stats and money cards count up the first time they scroll into view, and the
// room-to-build grid glows a few blocks at a time. The hero is a placeholder drawing until the real image exists
// (a loop rendered from our own 3D map, never satellite, Items 75 and 78).
import { useEffect, useRef, useState } from "react";
import { useInView } from "motion/react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Map as MapIcon } from "lucide-react";
import { AddressInput } from "../../components/AddressInput";
import { useAuthContext } from "../../contexts/AuthContext";
import { PanelMenuButton } from "../frame/AppFrame";
import { STROKE } from "../icons";
import { CountUp } from "../../components/CountUp";
import { Faq } from "../ui/Faq";

const EXAMPLE_ADDRESS = "1601 N Milwaukee Ave";

/** Room to build on the example grid: 0–3 = little → most, 9 = not known (hatched). */
const GRID = [0, 2, 1, 9, 3, 0, 1, 2, 0, 1, 1, 0, 3, 2, 0, 9, 0, 1, 3, 0, 2, 1, 0, 0, 1, 2, 3, 0, 9, 2, 9, 2, 1, 3, 0, 1, 0, 2, 1, 0, 0, 0, 2, 1, 3, 0, 2, 9, 0, 1];
const RAMP = ["var(--sc-r1)", "var(--sc-r2)", "var(--sc-r3)", "var(--sc-r4)"];

function useLocaleTag(): string {
  const { i18n } = useTranslation();
  return i18n.language.startsWith("es") ? "es-MX" : "en-US";
}

export default function LandingNextPage() {
  const { t, i18n } = useTranslation("next");
  const navigate = useNavigate();
  const { isAuthenticated, authRequired, signIn } = useAuthContext();
  const es = i18n.language.startsWith("es");
  const setLanguage = (lng: "en" | "es") => {
    i18n.changeLanguage(lng);
    try { localStorage.setItem("urbanlayer-language", lng); } catch { /* the choice still holds for this page */ }
  };
  const lookUp = (address: string) => navigate(`/scorecard?address=${encodeURIComponent(address)}`);

  return (
    <div className="ui-next nx-scene relative min-h-dvh bg-nx-page font-sans text-body text-nx-ink" data-ui-version="next" data-testid="landing">
      <header className="flex items-center gap-2 px-4 py-3 sm:gap-3 sm:px-8">
        <PanelMenuButton />
        <span className="truncate text-[1.0625rem] font-bold tracking-[-0.01em]">UrbanLayer</span>
        <span className="flex-1" />
        {/* On a phone, one button that switches to the other language (wireframe v5). */}
        <button type="button" lang={es ? "en" : "es"} onClick={() => setLanguage(es ? "en" : "es")} aria-label={t("frame.language")} className="rounded-full px-3 py-1.5 text-caption font-semibold ring-1 ring-nx-ink/15 touch-target sm:hidden">
          {es ? "EN" : "ES"}
        </button>
        <div role="group" aria-label={t("frame.language")} className="hidden overflow-hidden rounded-full ring-1 ring-nx-ink/15 text-caption sm:inline-flex">
          <button type="button" aria-pressed={!es} lang="en" onClick={() => setLanguage("en")} className={`px-3 py-1.5 touch-target ${!es ? "bg-nx-ink font-semibold text-nx-on-ink" : ""}`}>EN</button>
          <button type="button" aria-pressed={es} lang="es" onClick={() => setLanguage("es")} className={`px-3 py-1.5 touch-target ${es ? "bg-nx-ink font-semibold text-nx-on-ink" : ""}`}>ES</button>
        </div>
        {authRequired && !isAuthenticated ? (
          <button type="button" onClick={signIn} className="whitespace-nowrap rounded-full px-3 py-2 font-semibold ring-1 ring-nx-ink/20 hover:bg-nx-ink/5 touch-target sm:px-4">{t("frame.signIn")}</button>
        ) : (
          <Link to="/" className="whitespace-nowrap rounded-full px-3 py-2 font-semibold ring-1 ring-nx-ink/20 hover:bg-nx-ink/5 touch-target sm:px-4">{t("landing.openApp")}</Link>
        )}
      </header>

      <main>
        <section className="flex flex-col items-center gap-4 px-4 pt-10 text-center sm:pt-14">
          <h1 className="max-w-[760px] text-[2.25rem] font-bold leading-[1.05] tracking-[-0.03em] sm:text-[3.5rem]">{t("landing.headline")}</h1>
          <p className="max-w-[520px] text-[1.0625rem] nx-muted sm:text-[1.1875rem]">{t("landing.subline")}</p>
          <ExploreLink />
          <Hero />
        </section>

        <Stats />

        <Band kicker={t("landing.build.kicker")} title={t("landing.build.title")} body={t("landing.build.body")}>
          <BuildVisual />
        </Band>
        <Band reverse kicker={t("landing.city.kicker")} title={t("landing.city.title")} body={t("landing.city.body")}>
          <CityVisual />
        </Band>
        <Band kicker={t("landing.money.kicker")} title={t("landing.money.title")} body={t("landing.money.body")}>
          <MoneyVisual />
        </Band>
        <Band reverse kicker={t("landing.find.kicker")} title={t("landing.find.title")} body={t("landing.find.body")} action={<ExploreLink />}>
          <GridVisual />
        </Band>
        <Band kicker={t("landing.ask.kicker")} title={t("landing.ask.title")} analyst>
          <AnalystVisual />
        </Band>

        <div className="px-4 py-14">
          <Faq
            id="landing-faq"
            title={t("landing.faq.title")}
            items={(["free", "data", "coverage"] as const).map((k) => ({ key: k, q: t(`landing.faq.${k}.q`), a: t(`landing.faq.${k}.a`) }))}
          />
        </div>
      </main>

      <footer className="flex flex-wrap gap-x-10 gap-y-4 border-t border-nx-ink/10 px-4 pb-28 pt-7 text-caption nx-muted sm:px-8">
        <nav aria-label={t("landing.footer")} className="flex flex-wrap gap-4">
          <Link to="/discovery" className="hover:text-nx-ink">{t("nav.discovery")}</Link>
          <Link to="/pricing" className="hover:text-nx-ink">{t("landing.pricing")}</Link>
          <Link to="/about" className="hover:text-nx-ink">{t("landing.about")}</Link>
          <Link to="/privacy" className="hover:text-nx-ink">{t("landing.privacy")}</Link>
        </nav>
        <span className="flex-1" />
        <span>{t("landing.legal")}</span>
      </footer>

      {/* The page's one action, pinned to the bottom of the screen at every scroll position. */}
      <div className="sticky bottom-0 z-20 border-t border-nx-ink/10 bg-nx-page px-4 py-3 sm:px-8" data-testid="landing-bar">
        <div className="mx-auto max-w-[1200px]">
          <AddressInput
            variant="page"
            fullWidth
            dropUp
            defaultValue={EXAMPLE_ADDRESS}
            submitLabel={t("landing.showLot")}
            label={t("landing.addressLabel")}
            placeholder={t("landing.addressPlaceholder")}
            onSubmit={lookUp}
          />
        </div>
      </div>
    </div>
  );
}

function ExploreLink() {
  const { t } = useTranslation("next");
  return (
    <Link to="/discovery" className="inline-flex items-center gap-2 rounded-full px-4 py-2.5 font-semibold ring-1 ring-nx-ink/20 hover:bg-nx-ink/5 touch-target" data-testid="landing-explore">
      <MapIcon aria-hidden className="h-[18px] w-[18px]" strokeWidth={STROKE} />
      {t("landing.explore")}
    </Link>
  );
}

function Band({ kicker, title, body, reverse, analyst, action, children }: {
  kicker: string; title: string; body?: string; reverse?: boolean; analyst?: boolean; action?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section className={`mx-auto flex max-w-[1200px] gap-10 px-4 py-12 sm:py-14 ${reverse ? "flex-wrap-reverse" : "flex-wrap"} items-center`}>
      <div className={`flex min-w-0 flex-[1_1_320px] flex-col items-start gap-2.5 ${reverse ? "order-2" : ""}`}>
        <span className={`text-caption font-semibold ${analyst ? "text-nx-pill-purple" : "nx-muted"}`}>{kicker}</span>
        <h2 className="text-[1.75rem] font-bold leading-[1.15] tracking-[-0.02em] sm:text-[2.125rem]">{title}</h2>
        {body && <p className="nx-muted">{body}</p>}
        {action}
      </div>
      <div className={`min-w-0 flex-[999_1_520px] ${reverse ? "order-1" : ""}`}>{children}</div>
    </section>
  );
}

function ExampleTag() {
  const { t } = useTranslation("next");
  return <span className="text-caption nx-muted">{t("landing.example")}</span>;
}

/** The placeholder hero: one block in 3D, the lot in this-lot black (white in dark) with its zoning mass dashed above
    it, drifting slowly. */
function Hero() {
  const { t } = useTranslation("next");
  const f = (v: string) => ({ fill: `var(${v})` });
  return (
    <figure className="mt-6 flex w-full max-w-[1200px] flex-col gap-2">
      {/* The drift moves the whole picture as one composited layer (transform on a box, not on SVG shapes), so
          nothing re-renders frame by frame (owner's review: the drawing jittered). The label stays still on top. */}
      <div className="relative overflow-hidden rounded-[20px] bg-nx-block">
        <div className="motion-safe:animate-scene-drift [will-change:transform]">
        <svg viewBox="0 0 1200 460" role="img" aria-label={t("landing.heroAlt")} className="block h-auto w-full">
          <g>
            <path d="M0 300 L600 120 L1200 300 L600 480 Z" style={f("--sc-g1")} />
            <path d="M120 300 L600 156 L1080 300 L600 444 Z" style={f("--sc-g2")} />
            <path d="M330 237 L600 156 L870 237 L600 318 Z" fill="none" strokeWidth={10} style={{ stroke: "var(--sc-street)" }} />
            <path d="M225 268 L495 187 M705 187 L975 268 M495 349 L225 268 M975 268 L705 349" strokeWidth={10} style={{ stroke: "var(--sc-street)" }} />
            {[[300, 280, 60, 62, "b"], [420, 248, 50, 83, "b"], [690, 236, 50, 101, "p"], [800, 268, 60, 60, "b"], [440, 330, 60, 50, "n"], [650, 330, 60, 72, "b"]].map(([x, y, w, h, k]) => {
              const [X, Y, W, H] = [x as number, y as number, w as number, h as number];
              // An isometric box: the front face rises 0.3 per unit of width; every side face is 50 wide, falling 15.
              const r = W * 0.3;
              return (
                <g key={`${X}-${Y}`}>
                  <path d={`M${X} ${Y} L${X + W} ${Y - r} L${X + W} ${Y - r - H} L${X} ${Y - H} Z`} style={f(`--sc-${k}1`)} />
                  <path d={`M${X + W} ${Y - r} L${X + W + 50} ${Y - r + 15} L${X + W + 50} ${Y - r + 15 - H} L${X + W} ${Y - r - H} Z`} style={f(`--sc-${k}2`)} />
                  <path d={`M${X} ${Y - H} L${X + W} ${Y - r - H} L${X + W + 50} ${Y - r + 15 - H} L${X + 50} ${Y + 15 - H} Z`} style={f(`--sc-${k}3`)} />
                </g>
              );
            })}
            <path d="M560 300 L610 285 L610 248 L560 263 Z" className="fill-nx-lot" />
            <path d="M610 285 L650 297 L650 260 L610 248 Z" style={f("--sc-lot-side")} />
            <path d="M560 263 L610 248 L650 260 L600 275 Z" style={f("--sc-lot-top")} />
            <path d="M560 300 L610 285 L610 150 L560 165 Z M610 285 L650 297 L650 162 L610 150 Z M560 165 L610 150 L650 162 L600 177 Z" className="fill-nx-lot/[0.07] stroke-nx-lot" strokeWidth={2} strokeDasharray="7 5" />
          </g>
        </svg>
        </div>
        <div aria-hidden className="absolute left-[56.5%] top-[31.5%] hidden flex-col rounded-xl bg-nx-page px-3 py-2 text-left shadow-[0_2px_10px_rgb(0_0_0/0.12)] ring-1 ring-nx-ink/15 sm:flex">
          <span className="text-caption font-semibold">{t("landing.heroAllowed")}</span>
          <span className="text-caption nx-muted">{t("landing.heroBuilt")}</span>
        </div>
      </div>
    </figure>
  );
}

function Stats() {
  const { t } = useTranslation("next");
  const locale = useLocaleTag();
  const items = [
    { key: "sources", value: 25, suffix: "+", card: "bg-nx-stat-a" },
    { key: "sections", value: 14500, suffix: "", card: "bg-nx-stat-b" },
    { key: "lots", value: 880000, suffix: "", card: "bg-nx-stat-a" },
    { key: "areas", value: 77, suffix: "", card: "bg-nx-stat-b" },
  ];
  return (
    <section aria-label={t("landing.stats.label")} className="mx-auto max-w-[1200px] px-4 pb-6 pt-16 sm:pt-20">
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4" data-testid="landing-stats">
        {items.map((s, i) => (
          <div key={s.key} className={`flex flex-col gap-1.5 rounded-2xl p-4 text-nx-card-ink sm:p-6 ${s.card}`}>
            <span className="text-caption font-semibold">{t(`landing.stats.${s.key}`)}</span>
            {/* The final figure for screen readers; the counting one is decoration. */}
            <span className="sr-only">{`${s.value.toLocaleString(locale)}${s.suffix}`}</span>
            {/* The original landing's count-up (components/CountUp): starts on scroll-in, staggered. */}
            <span aria-hidden className="text-[1.75rem] font-bold tabular-nums tracking-[-0.02em] sm:text-[2.5rem]">
              <CountUp to={s.value} delay={i * 0.15} format={(n) => `${n.toLocaleString(locale)}${s.suffix}`} />
            </span>
            <span className="hidden text-caption text-nx-card-ink/70 sm:block">{t(`landing.stats.${s.key}Note`)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

/** A built-vs-allowed bar that fills from empty the first time it scrolls into view (owner, 2026-11-12). */
function Bar({ label, share, value, shown, delay }: { label: string; share: number; value: string; shown: boolean; delay: number }) {
  return (
    <>
      <span>{label}</span>
      <div className="relative h-3.5 rounded-full bg-nx-ink/10">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-nx-lot motion-safe:transition-[width] motion-safe:duration-[1400ms] motion-safe:ease-[cubic-bezier(0.16,1,0.3,1)]"
          style={{ width: shown ? `${share}%` : "0%", transitionDelay: `${delay}s` }}
        />
      </div>
      <span className="font-semibold">{value}</span>
    </>
  );
}

function BuildVisual() {
  const { t } = useTranslation("next");
  const ref = useRef<HTMLDivElement | null>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });
  return (
    <div className="flex flex-col gap-3.5 rounded-[20px] bg-nx-block p-5 sm:p-6">
      <ExampleTag />
      <div ref={ref} className="grid grid-cols-[80px_minmax(0,1fr)_88px] items-center gap-x-3.5 gap-y-2.5 text-caption sm:text-body" data-testid="landing-bars">
        <Bar label={t("landing.build.units")} share={34} value={t("landing.build.unitsValue")} shown={inView} delay={0} />
        <Bar label={t("landing.build.floor")} share={52} value="52%" shown={inView} delay={0.15} />
        <Bar label={t("landing.build.height")} share={53} value={t("landing.build.heightValue")} shown={inView} delay={0.3} />
      </div>
      <span className="text-caption nx-muted">{t("landing.build.note")}</span>
    </div>
  );
}

function CityVisual() {
  const { t } = useTranslation("next");
  return (
    <div className="flex flex-col gap-3 rounded-[20px] bg-nx-block p-5 sm:p-6">
      <ExampleTag />
      <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-nx-page p-4">
        <span className="rounded-full bg-nx-pill-yellow-bg px-2.5 py-0.5 text-caption font-semibold text-nx-pill-yellow">{t("landing.city.pending")}</span>
        <span className="font-semibold">{t("landing.city.rezoning")}</span>
        <span className="text-caption nx-muted">{t("landing.city.rezoningNote")}</span>
      </div>
      <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-nx-page p-4">
        <span className="rounded-full bg-nx-pill-green-bg px-2.5 py-0.5 text-caption font-semibold text-nx-pill-green">{t("landing.city.applies")}</span>
        <span className="font-semibold">{t("landing.city.coach")}</span>
        <span className="text-caption nx-muted">{t("landing.city.coachNote")}</span>
      </div>
    </div>
  );
}

function MoneyVisual() {
  const { t } = useTranslation("next");
  const locale = useLocaleTag();
  const cards = [
    { key: "sale", value: 240, card: "bg-nx-stat-a" },
    { key: "rent", value: 1850, card: "bg-nx-stat-b" },
    { key: "tax", value: 8420, card: "bg-nx-stat-a" },
  ];
  return (
    <div className="flex flex-col gap-2">
      <ExampleTag />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {cards.map((c, i) => (
          <div key={c.key} className={`flex flex-col gap-1 rounded-2xl p-4 text-nx-card-ink ${c.card}`}>
            <span className="text-caption font-semibold">{t(`landing.money.${c.key}`)}</span>
            <span className="sr-only">{t(`landing.money.${c.key}Value`, { value: c.value.toLocaleString(locale) })}</span>
            <span aria-hidden className="text-[1.625rem] font-bold tabular-nums">
              <CountUp to={c.value} delay={i * 0.15} format={(n) => t(`landing.money.${c.key}Value`, { value: n.toLocaleString(locale) })} />
            </span>
            <span className="text-caption text-nx-card-ink/70">{t(`landing.money.${c.key}Note`)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function GridVisual() {
  const { t } = useTranslation("next");
  return (
    <div className="flex flex-col gap-3 rounded-[20px] bg-nx-block p-4">
      <div role="img" aria-label={t("landing.find.gridAlt")} className="grid grid-cols-10 gap-1.5">
        {GRID.map((v, i) => (
          <div
            key={i}
            className={v === 9 ? "nx-hatched h-7 rounded sm:h-10" : "h-7 rounded motion-safe:animate-block-glow sm:h-10"}
            style={v === 9 ? undefined : { background: RAMP[v], animationDelay: `${((i % 10) + Math.floor(i / 10)) * 0.45}s` }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-4 text-caption">
        <span className="inline-flex items-center gap-1.5"><i aria-hidden className="h-3 w-3 rounded-sm" style={{ background: RAMP[0] }} />{t("landing.find.little")}</span>
        <span className="inline-flex items-center gap-1.5"><i aria-hidden className="h-3 w-3 rounded-sm" style={{ background: RAMP[3] }} />{t("landing.find.most")}</span>
        <span className="inline-flex items-center gap-1.5"><i aria-hidden className="nx-hatched h-3 w-3 rounded-sm" />{t("landing.find.unknown")}</span>
      </div>
    </div>
  );
}

/** The analyst's exchange: the question types itself, the answer appears, then it loops. Reduced motion: it sits. */
function AnalystVisual() {
  const { t } = useTranslation("next");
  const question = t("landing.ask.question");
  const [shown, setShown] = useState(question.length);
  const [answered, setAnswered] = useState(true);
  useEffect(() => {
    let reduce = false;
    try { reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { /* keep motion */ }
    if (reduce) return;
    let timer = 0;
    const run = () => {
      setAnswered(false);
      let i = 0;
      const type = () => {
        i += 1;
        setShown(i);
        if (i < question.length) { timer = window.setTimeout(type, 45); return; }
        timer = window.setTimeout(() => { setAnswered(true); timer = window.setTimeout(run, 7000); }, 450);
      };
      setShown(0);
      timer = window.setTimeout(type, 400);
    };
    timer = window.setTimeout(run, 2500);
    return () => window.clearTimeout(timer);
  }, [question]);
  const pill = "inline-block rounded-full bg-nx-pill-purple-bg px-1.5 text-caption font-semibold text-nx-pill-purple";
  return (
    <div className="nx-ai-edge rounded-[22px]" style={{ padding: 2 }}>
      <div className="flex flex-col gap-3.5 rounded-[20px] bg-nx-page p-6" aria-hidden>
        <div className="min-h-[2.5rem] max-w-[85%] self-end rounded-2xl bg-nx-ink/[0.06] px-3.5 py-2.5">{question.slice(0, shown)}</div>
        <p className={`transition-opacity duration-500 ${answered ? "opacity-100" : "opacity-0"}`}>
          <strong>{t("landing.ask.lead")}</strong> {t("landing.ask.answer1")} <span className={pill}>1</span>{t("landing.ask.answer2")} <span className={pill}>2</span>.
        </p>
        <div className={`flex flex-wrap gap-2 text-caption transition-opacity duration-500 ${answered ? "opacity-100" : "opacity-0"}`}>
          <span className="rounded-xl px-2.5 py-1.5 ring-1 ring-nx-ink/10">{t("landing.ask.chipLot")}</span>
          <span className="rounded-xl px-2.5 py-1.5 ring-1 ring-nx-ink/10">{t("landing.ask.chipMap")}</span>
          <span className="rounded-xl px-2.5 py-1.5 ring-1 ring-nx-ink/10">{t("landing.ask.chipSources")}</span>
        </div>
      </div>
      <p className="sr-only">{`${question} ${t("landing.ask.lead")} ${t("landing.ask.answer1")}${t("landing.ask.answer2")}.`}</p>
    </div>
  );
}
