// "Corrections": the review queue for building facts visitors say are wrong (decision Item 129 §4, PR 4). One report per
// card: the lot's block and Street View, what the card showed (and shows now, when it moved), what the reporter says,
// whether they were signed in and how their past reports went, other open reports on the lot. Accept asks what to apply
// (the stories you see, prefilled from the report; no building; or nothing, a case for the Assessor). Nothing is applied
// from here: "Export accepted" gives the file `backend/discovery/user_corrections.json` and its diff for a PR, and the
// next index build reads it. English-only, like the rest of /admin.
import { useCallback, useEffect, useState } from "react";
import {
  Building2, Check, CircleAlert, CircleCheck, Copy, Download, Eraser, FileDiff, History, Info, Landmark, Layers, MapPinned,
  PersonStanding, UserRound, UserRoundX, VolumeX, X,
} from "lucide-react";
import {
  exportAdminCorrections, fetchAdminCorrections, reviewAdminCorrection,
  type AdminCorrection, type AdminCorrectionExport, type AdminCorrectionReview, type CorrectionStatus,
} from "../../lib/api";
import { titleCaseAddress } from "../../lib/format";
import { googleMapsUrl, streetViewUrl } from "../map/mapInfo";
import { BlockSlice } from "../ui/BlockSlice";
import { Block, Pill } from "../ui/Blocks";
import { Empty, IconAction } from "./adminUi";
import { familyOf } from "../saved/savedModel";
import { defaultApply, reportWords } from "./correctionsModel";
import { STROKE } from "../icons";

const TABS: Array<[CorrectionStatus, string]> = [["new", "Open"], ["accepted", "Accepted"], ["rejected", "Rejected"], ["duplicate", "Duplicates"]];
const inputCls = "rounded-lg bg-nx-page px-2.5 text-caption text-nx-ink ring-1 ring-nx-ink/15 placeholder:text-nx-ink/50 focus:outline-none focus:ring-nx-ink/60";
const buttonCls = "inline-flex h-8 items-center gap-1.5 rounded-lg border border-nx-ink/10 px-3 text-caption hover:bg-nx-ink/5 disabled:opacity-50 touch-target";

const SOURCE_WORDS: Record<string, string> = {
  footprint: "footprint × stories estimate", assessor: "Assessor", assessor_condo: "Assessor (condo units)",
  commercial_valuation: "Assessor's commercial records", city_land_inventory: "City land inventory", empty_lot: "empty lot",
};
const sqft = (v: number | null | undefined) => (v == null ? "not known" : `${Math.round(v).toLocaleString("en-US")} sq ft`);
const when = (ms: number) => new Date(ms).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

export function CorrectionsSection() {
  const [tab, setTab] = useState<CorrectionStatus>("new");
  const [loaded, setLoaded] = useState<{ key: string; data: { reports: AdminCorrection[]; total: number } | "failed" } | null>(null);
  const [seq, setSeq] = useState(0);
  const [exported, setExported] = useState<AdminCorrectionExport | null | "failed">(null);
  const key = `${tab}:${seq}`;
  useEffect(() => {
    let live = true;
    fetchAdminCorrections(tab).then((d) => { if (live) setLoaded({ key, data: d ?? "failed" }); });
    return () => { live = false; };
  }, [tab, key]);
  const data = loaded?.key === key ? loaded.data : null;
  const load = useCallback(() => setSeq((n) => n + 1), []);

  return (
    <div className="flex flex-col gap-4" data-testid="corrections-section">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div role="tablist" aria-label="Reports" className="inline-flex rounded-xl bg-nx-ink/5 p-1">
          {TABS.map(([s, label]) => (
            <button key={s} type="button" role="tab" aria-selected={tab === s} onClick={() => setTab(s)}
              className={`rounded-lg px-3 py-1 text-caption touch-target ${tab === s ? "bg-nx-page font-semibold shadow-sm" : "nx-muted hover:text-nx-ink"}`}>
              {label}{tab === s && data && data !== "failed" ? ` · ${data.total}` : ""}
            </button>
          ))}
        </div>
        <button type="button" className={buttonCls} onClick={() => exportAdminCorrections().then((e) => setExported(e ?? "failed"))} data-testid="corrections-export">
          <FileDiff aria-hidden className="h-4 w-4" strokeWidth={STROKE} />Export accepted
        </button>
      </div>
      {exported && <ExportPanel exported={exported} onClose={() => setExported(null)} />}
      <Block>
        {data === null && <p className="text-caption nx-muted">Loading reports…</p>}
        {data === "failed" && <Empty icon={CircleAlert}>Couldn't load the reports.</Empty>}
        {data && data !== "failed" && data.reports.length === 0 && (
          <Empty icon={CircleCheck}>{tab === "new" ? "No open reports." : "None yet."}</Empty>
        )}
        {data && data !== "failed" && data.reports.length > 0 && (
          <ul className="flex flex-col divide-y divide-nx-ink/10">
            {data.reports.map((r) => <ReportRow key={r.id} report={r} onReviewed={load} />)}
          </ul>
        )}
      </Block>
    </div>
  );
}

function addressOf(r: AdminCorrection): string {
  const a = r.now?.address;
  if (!a) return `PIN ${r.pin10}`;
  return a.startsWith("~") ? `Near ${titleCaseAddress(a.slice(1))}` : titleCaseAddress(a);
}

/** One report on one row: the lot's block, the address with who sent it, what they say, what the card showed, and
    the actions as icons. Accepting, rejecting or marking a duplicate opens a small form under the row. */
function ReportRow({ report: r, onReviewed }: { report: AdminCorrection; onReviewed: () => void }) {
  const [mode, setMode] = useState<AdminCorrectionReview["action"] | null>(null);
  const lat = r.now?.lat, lon = r.now?.lon;
  const source = r.shown.bldg_sqft_source ? SOURCE_WORDS[r.shown.bldg_sqft_source] ?? r.shown.bldg_sqft_source : null;
  const hasPast = r.past.accepted + r.past.rejected > 0;
  return (
    <li className="flex flex-col gap-3 py-3" data-testid="correction-report">
      <div className="flex flex-wrap items-start gap-3">
        <BlockSlice pin10={r.pin10} zoneTag={null} family={familyOf(r.now?.zone_class)} className="h-16 w-16 shrink-0 rounded-xl" />
        <div className="flex min-w-0 flex-1 basis-[12rem] flex-col gap-1.5">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-semibold">{addressOf(r)}</span>
            <span title={r.signed_in ? "Signed in" : "Signed out"} className="inline-flex">
              {r.signed_in
                ? <UserRound aria-label="Signed in" className="h-4 w-4 text-nx-pill-green" strokeWidth={STROKE} />
                : <UserRoundX aria-label="Signed out" className="h-4 w-4 nx-muted" strokeWidth={STROKE} />}
            </span>
            <span className="text-caption nx-muted">{when(r.created_at)}</span>
          </p>
          <p className="flex flex-wrap gap-1.5">
            {reportWords(r).map((w) => <Pill key={w} tone="blue">{w}</Pill>)}
            {r.muted && <Pill tone="yellow" icon={VolumeX}>Muted</Pill>}
            {hasPast && <Pill icon={History}>{r.past.accepted} accepted, {r.past.rejected} rejected</Pill>}
            {r.others_open.length > 0 && <Pill icon={Layers}>{r.others_open.map((i) => `#${i}`).join(", ")} also open</Pill>}
          </p>
          {r.note && <p className="line-clamp-2 text-caption [overflow-wrap:anywhere]" title={r.note}>“{r.note}”</p>}
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption nx-muted">
            <span className="inline-flex items-center gap-1"><Layers aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{sqft(r.shown.bldg_sqft)}{source ? ` · ${source}` : ""}</span>
            {r.changed && r.now && <span data-testid="correction-changed"><Pill tone="yellow">Now {sqft(r.now.bldg_sqft)}</Pill></span>}
            {r.status !== "new" && <span className="inline-flex items-center gap-1"><Check aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{r.status}{r.applied ? `, ${appliedWords(r.applied)}` : ""}{r.review_note ? `: “${r.review_note}”` : ""}</span>}
          </p>
        </div>
        <div className="ml-auto flex shrink-0 flex-wrap items-center justify-end gap-0.5">
          {lat != null && lon != null && <IconAction label="Street View" icon={PersonStanding} href={streetViewUrl(lat, lon)} />}
          {lat != null && lon != null && <IconAction label="Map" icon={MapPinned} href={googleMapsUrl(lat, lon)} />}
          {r.status === "new" && (
            <>
              <span aria-hidden className="mx-1 h-5 w-px bg-nx-ink/10" />
              <IconAction label="Accept" icon={Check} onClick={() => setMode("accept")} pressed={mode === "accept"} testId="correction-accept" />
              <IconAction label="Reject" icon={X} onClick={() => setMode("reject")} pressed={mode === "reject"} testId="correction-reject" />
              <IconAction label="Duplicate" icon={Copy} onClick={() => setMode("duplicate")} pressed={mode === "duplicate"} testId="correction-duplicate" />
            </>
          )}
        </div>
      </div>
      {mode && <ReviewForm key={mode} report={r} mode={mode} onCancel={() => setMode(null)} onReviewed={onReviewed} />}
    </li>
  );
}

function appliedWords(a: NonNullable<AdminCorrection["applied"]>): string {
  if (a.stories) return `applies ${a.stories} stories`;
  if (a.empty) return "applies no building";
  return "nothing applied (a case for the Assessor)";
}

function ReviewForm({ report: r, mode, onCancel, onReviewed }: {
  report: AdminCorrection; mode: AdminCorrectionReview["action"]; onCancel: () => void; onReviewed: () => void;
}) {
  const init = defaultApply(r);
  const [apply, setApply] = useState(init.apply);
  const [stories, setStories] = useState(init.stories);
  const [reason, setReason] = useState(mode === "duplicate" && r.others_open.length ? `Duplicate of #${r.others_open[0]}` : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const storiesOk = /^\d{1,3}$/.test(stories) && Number(stories) >= 1 && Number(stories) <= 150;
  const ready = mode !== "accept" || apply !== "stories" || storiesOk;

  async function save() {
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      await reviewAdminCorrection(r.id, {
        action: mode,
        ...(reason.trim() ? { reason: reason.trim().slice(0, 200) } : {}),
        ...(mode === "accept" ? { apply, ...(apply === "stories" ? { stories: Number(stories) } : {}) } : {}),
      });
      onReviewed();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  const choice = (value: typeof apply, label: string, Icon: typeof Check) => (
    <button type="button" role="radio" aria-checked={apply === value} onClick={() => setApply(value)}
      className={`inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-caption touch-target ${apply === value ? "bg-nx-ink font-medium text-nx-on-ink" : "bg-nx-ink/5 hover:bg-nx-ink/10"}`}>
      <Icon aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{label}
    </button>
  );

  return (
    <form className="ml-0 flex flex-col gap-3 rounded-2xl bg-nx-ink/[0.03] p-3 sm:ml-[4.75rem]" onSubmit={(e) => { e.preventDefault(); void save(); }} data-testid="correction-review">
      {mode === "accept" && (
        <div className="flex flex-col gap-2">
          <div role="radiogroup" aria-label="Apply" className="flex flex-wrap items-center gap-1.5">
            {choice("stories", "Stories", Building2)}
            {choice("empty", "No building", Eraser)}
            {choice("none", "Nothing", Landmark)}
            {apply === "stories" && (
              <input type="text" inputMode="numeric" maxLength={3} value={stories} aria-label="Stories to apply" autoFocus
                onChange={(e) => setStories(e.target.value.replace(/\D/g, ""))} className={`${inputCls} h-8 w-16 text-center`} />
            )}
          </div>
          <p className="flex items-center gap-1.5 text-caption nx-muted"><Info aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
            {apply === "none" ? "Kept as a case for the Assessor." : "Replaces only the footprint estimate."}</p>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <input type="text" maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)}
          placeholder={mode === "reject" ? "Why (optional)" : "What you saw (optional)"} aria-label="Reason" className={`${inputCls} h-8 min-w-0 flex-1`} />
        <button type="submit" disabled={!ready || busy} className={`${buttonCls} border-transparent bg-nx-ink font-semibold text-nx-on-ink`} data-testid="correction-review-save">
          {mode === "accept" ? "Accept" : mode === "reject" ? "Reject" : "Mark duplicate"}
        </button>
        <button type="button" className={buttonCls} onClick={onCancel}>Cancel</button>
      </div>
      {error && <p role="alert" className="text-caption text-nx-pill-red">{error}</p>}
    </form>
  );
}

function ExportPanel({ exported, onClose }: { exported: AdminCorrectionExport | "failed"; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  if (exported === "failed") return <p className="text-caption text-nx-pill-red">Couldn't build the export.</p>;
  const download = () => {
    const url = URL.createObjectURL(new Blob([exported.content], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "user_corrections.json" });
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-nx-ink/10 bg-nx-page p-3 text-caption" data-testid="corrections-export-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p>
          <span className="font-semibold">{exported.entries} {exported.entries === 1 ? "lot" : "lots"}</span> in the file
          {exported.new_reports ? `, ${exported.new_reports} newly accepted ${exported.new_reports === 1 ? "report" : "reports"}` : ", nothing new since the committed copy"}.
          Commit it as <code>backend/discovery/user_corrections.json</code> in a PR; the next index build applies it.
        </p>
        <div className="flex gap-1.5">
          <button type="button" className={buttonCls} onClick={download}><Download aria-hidden className="h-4 w-4" strokeWidth={STROKE} />Download file</button>
          <button type="button" className={buttonCls} onClick={() => { void navigator.clipboard?.writeText(exported.diff); setCopied(true); }}>
            <Copy aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{copied ? "Copied" : "Copy diff"}
          </button>
          <button type="button" className={buttonCls} onClick={onClose} aria-label="Close export"><X aria-hidden className="h-4 w-4" strokeWidth={STROKE} /></button>
        </div>
      </div>
      <pre className="max-h-72 overflow-auto rounded-lg bg-nx-block p-2 font-mono text-micro" data-testid="corrections-diff">{exported.diff || "No changes."}</pre>
    </div>
  );
}
