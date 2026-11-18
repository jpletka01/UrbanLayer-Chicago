// "Code updates": how old our Municipal Code text is, what the City Council passed since, and whether the daily check
// of the City Clerk is running (owner's review 2026-11-17: show, don't tell; a few words per line; "Title 17" means
// nothing, so it is "Zoning code"). One status, four figures, the checker's state as pills, the amendments as one-line
// rows (the summary opens on a click), and the titles that need a hand behind one expand. Read-only, from
// /api/admin/code-currency (no network on the server side). English only, like the rest of /admin.
import { useEffect, useState } from "react";
import {
  CalendarClock, ChevronDown, CircleAlert, CircleCheck, CircleDashed, FileClock, Hand, Landmark, MapPinOff, RefreshCw,
  Scale, SquareArrowOutUpRight,
} from "lucide-react";
import { fetchAdminCodeCurrency, type AdminCodeCurrency } from "../../lib/api";
import { amendmentStatus, formatDay } from "../../lib/format";
import type { Amendment } from "../../lib/types";
import { STROKE } from "../icons";
import { Block, Pill, StatTile, type PillTone } from "../ui/Blocks";
import { CODE_STATUS_WORD } from "./adminModel";
import { Empty, IconAction, Tiles } from "./adminUi";

const STATUS_TONE: Record<AdminCodeCurrency["code"]["status"], PillTone> = { green: "green", amber: "yellow", red: "red" };
const REVIEW = {
  applied: { word: "Applied", tone: "green" as PillTone, icon: CircleCheck },
  none: { word: "No effect", tone: "gray" as PillTone, icon: CircleCheck },
  pending: { word: "To review", tone: "yellow" as PillTone, icon: CircleDashed },
};
const ICON = "h-5 w-5";
// The newest amendments first; the rest behind "Show all".
const FIRST_ROWS = 6;
const days = (n: number | null | undefined) => (n == null ? null : `${n} ${n === 1 ? "day" : "days"}`);

export function CodeCurrencySection() {
  const [data, setData] = useState<AdminCodeCurrency | null | undefined>(undefined);
  const [showAll, setShowAll] = useState(false);
  useEffect(() => { fetchAdminCodeCurrency().then(setData); }, []);

  if (data === undefined) return <p className="text-caption nx-muted">Loading…</p>;
  if (data === null) return <Empty icon={CircleAlert}>Code status isn't available right now.</Empty>;

  const { code, clerk, amendments, map_lag: lag, designations: desig } = data;
  const unknown = code.check_state === "unknown";
  const handWork = [...(lag?.unparsed ?? []), ...(desig?.unparsed ?? [])];
  return (
    <div className="flex flex-col gap-4" data-testid="code-currency">
      <div className="flex flex-wrap items-center gap-2">
        <span data-testid="code-status"><Pill tone={STATUS_TONE[code.status]} icon={code.status === "green" ? CircleCheck : CircleAlert}>{CODE_STATUS_WORD[code.status]}</Pill></span>
        <CheckerPills code={code} clerk={clerk} />
      </div>

      <Tiles testId="code-tiles">
        <StatTile tone="a" icon={<CalendarClock className={ICON} strokeWidth={STROKE} />} label="Code text age"
          figure={code.age_days ?? "—"} unit={code.age_days != null ? "days" : undefined}
          note={code.as_of ? `Through ${formatDay(code.as_of)}` : "Date unknown"} />
        <StatTile tone="b" icon={<Scale className={ICON} strokeWidth={STROKE} />} label="Zoning changes since"
          figure={<span data-testid="code-title17">{unknown || code.lag.title17_passed_since == null ? "—" : code.lag.title17_passed_since}</span>}
          note={unknown ? "Not checked lately" : code.lag.unreviewed ? `${code.lag.unreviewed} to review` : "All reviewed"} />
        <StatTile tone="b" icon={<MapPinOff className={ICON} strokeWidth={STROKE} />} label="Rezonings off the map"
          figure={<span data-testid="map-lag-count">{lag?.passed_not_on_map ?? "—"}</span>}
          note={lag ? (lag.passed_not_on_map == null ? "Never checked" : lag.oldest_days != null ? `Oldest ${days(lag.oldest_days)}` : "None waiting") : "Not reported"} />
        <StatTile tone="a" icon={<Landmark className={ICON} strokeWidth={STROKE} />} label="New landmarks"
          figure={<span data-testid="designations-count">{desig?.passed ?? "—"}</span>}
          note={desig ? (desig.passed == null ? "Never checked" : `Last 180 days · ${desig.with_parcels ?? 0} placed`) : "Not reported"} />
      </Tiles>

      {(clerk.last_error || lag?.last_error || desig?.last_error || clerk.contract_problems.length > 0) && (
        <ul className="flex flex-col gap-1 rounded-2xl bg-nx-pill-red-bg px-4 py-3 text-caption text-nx-pill-red" data-testid="code-errors">
          {[clerk.last_error, lag?.last_error, desig?.last_error, ...clerk.contract_problems].filter(Boolean).map((e) => (
            <li key={e!} className="flex items-start gap-2 [overflow-wrap:anywhere]"><CircleAlert aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} />{e}</li>
          ))}
        </ul>
      )}

      <Block title="Passed since our text" icon={FileClock} aside={amendments.length ? `${amendments.length}` : undefined}>
        {amendments.length ? (
          <>
            <ul className="flex flex-col divide-y divide-nx-ink/10" data-testid="code-amendments-table">
              {(showAll ? amendments : amendments.slice(0, FIRST_ROWS)).map((a) => <AmendmentRow key={a.record} a={a} />)}
            </ul>
            {amendments.length > FIRST_ROWS && (
              <button type="button" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}
                className="inline-flex items-center gap-1.5 self-start text-caption font-medium nx-muted hover:text-nx-ink touch-target" data-testid="code-show-all">
                <ChevronDown aria-hidden className={`h-4 w-4 transition-transform ${showAll ? "rotate-180" : ""}`} strokeWidth={STROKE} />
                {showAll ? "Show fewer" : `Show all ${amendments.length}`}
              </button>
            )}
          </>
        ) : <Empty icon={CircleCheck}>Nothing passed since.</Empty>}
      </Block>

      {handWork.length > 0 && (
        <details className="group rounded-2xl bg-nx-block px-5 py-4" data-testid="code-hand-work">
          <summary className="flex cursor-pointer list-none items-center gap-2 font-semibold">
            <Hand aria-hidden className="h-4 w-4" strokeWidth={STROKE} />Titles to place by hand
            <Pill tone="yellow">{handWork.length}</Pill>
            <ChevronDown aria-hidden className="ml-auto h-4 w-4 transition-transform group-open:rotate-180" strokeWidth={STROKE} />
          </summary>
          <div className="mt-3 flex flex-col gap-2 text-caption">
            {lag && lag.unparsed.length > 0 && <p data-testid="map-lag"><span className="nx-muted">Rezonings, in rezoning_overrides.json: </span><span className="font-mono">{lag.unparsed.join(", ")}</span></p>}
            {desig && desig.unparsed.length > 0 && <p data-testid="designations"><span className="nx-muted">Landmarks, not flagged: </span><span className="font-mono">{desig.unparsed.join(", ")}</span></p>}
          </div>
        </details>
      )}
    </div>
  );
}

/** The daily Clerk check in three pills: is it fresh, when did it last work, how many failures in a row. */
function CheckerPills({ code, clerk }: Pick<AdminCodeCurrency, "code" | "clerk">) {
  const fresh = code.check_state === "fresh";
  return (
    <>
      <Pill tone={fresh ? "green" : code.check_state === "aging" ? "yellow" : "red"} icon={RefreshCw}>
        {fresh ? "Clerk checked" : code.check_state === "aging" ? "Clerk check aging" : "Clerk not checked"}
      </Pill>
      <Pill icon={CalendarClock}>{clerk.last_success ? `Last worked ${formatDay(clerk.last_success)}` : "Never worked"}</Pill>
      {clerk.consecutive_failures > 0 && <Pill tone="red" icon={CircleAlert}>{clerk.consecutive_failures} failed in a row</Pill>}
    </>
  );
}

/** One amendment on one line: when, what it does (its reviewed summary, else the Council's title), zoning or other
    code, reviewed or not, and the Clerk's record behind an icon. A click opens the whole text. */
function AmendmentRow({ a }: { a: Amendment }) {
  const [open, setOpen] = useState(false);
  const review = REVIEW[amendmentStatus(a)];
  const text = a.summary || a.title;
  return (
    <li className="flex items-start gap-3 py-2.5 text-caption">
      <span className="w-14 shrink-0 pt-px tabular-nums nx-muted">{shortDay(a.passed_on)}</span>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className={`min-w-0 flex-1 text-left ${open ? "" : "line-clamp-1"}`} title={open ? undefined : text}>
        {text}
      </button>
      <span className="flex shrink-0 items-center gap-1.5">
        <Pill tone={a.relevance === "title17" ? "blue" : "gray"}>{a.relevance === "title17" ? "Zoning" : "Other code"}</Pill>
        <Pill tone={review.tone} icon={review.icon}>{review.word}</Pill>
        {a.url
          ? <IconAction label={`Clerk record ${a.record}`} icon={SquareArrowOutUpRight} href={a.url} />
          : <span className="w-8" aria-hidden />}
      </span>
    </li>
  );
}

function shortDay(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
