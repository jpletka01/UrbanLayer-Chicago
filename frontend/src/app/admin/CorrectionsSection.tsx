// "Corrections": the review queue for building facts visitors say are wrong (decision Item 129 §4, PR 4). One report per
// card: the lot's block and Street View, what the card showed (and shows now, when it moved), what the reporter says,
// whether they were signed in and how their past reports went, other open reports on the lot. Accept asks what to apply
// (the stories you see, prefilled from the report; no building; or nothing, a case for the Assessor). Nothing is applied
// from here: "Export accepted" gives the file `backend/discovery/user_corrections.json` and its diff for a PR, and the
// next index build reads it. English-only, like the rest of /admin.
import { useCallback, useEffect, useState } from "react";
import { Check, Copy, Download, FileDiff, MapPinned, PersonStanding, UserRound, UserRoundX, X } from "lucide-react";
import {
  exportAdminCorrections, fetchAdminCorrections, reviewAdminCorrection,
  type AdminCorrection, type AdminCorrectionExport, type AdminCorrectionReview, type CorrectionStatus,
} from "../../lib/api";
import { titleCaseAddress } from "../../lib/format";
import { googleMapsUrl, streetViewUrl } from "../map/mapInfo";
import { BlockSlice } from "../ui/BlockSlice";
import { familyOf } from "../saved/savedModel";
import { STROKE } from "../icons";

const TABS: Array<[CorrectionStatus, string]> = [["new", "Open"], ["accepted", "Accepted"], ["rejected", "Rejected"], ["duplicate", "Duplicates"]];
const inputCls = "px-2.5 py-1.5 rounded-md bg-nx-page border border-nx-ink/10 text-caption text-nx-ink placeholder:nx-muted focus:outline-none focus:border-nx-ink/60";
const buttonCls = "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-nx-ink/10 text-caption hover:border-nx-ink/30 disabled:opacity-50";
const pill = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-micro";

const SOURCE_WORDS: Record<string, string> = {
  footprint: "footprint × stories estimate", assessor: "Assessor", assessor_condo: "Assessor (condo units)",
  commercial_valuation: "Assessor's commercial records", city_land_inventory: "City land inventory", empty_lot: "empty lot",
};
const sqft = (v: number | null | undefined) => (v == null ? "not known" : `${Math.round(v).toLocaleString("en-US")} sq ft`);
const when = (ms: number) => new Date(ms).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

/** What the reporter says, in words: "Stories: 20", "Floor area too high", "No building now" / "It's a condo" by what
 * the card showed (the two building and the two condo chips share a kind; the snapshot says which way). */
export function reportWords(r: Pick<AdminCorrection, "kinds" | "stories" | "area_dir" | "shown" | "now">): string[] {
  // The snapshot says what the card showed (reports sent before it carried these fall back to the index today).
  const structure = r.shown.structure !== undefined ? r.shown.structure : r.now?.structure;
  const condo = r.shown.condo !== undefined ? r.shown.condo : r.now?.condo;
  const hadBuilding = structure !== "empty";
  return r.kinds.map((k) => {
    if (k === "stories") return `Stories: ${r.stories ?? "?"}`;
    if (k === "area") return `Floor area too ${r.area_dir ?? "?"}`;
    if (k === "gone") return hadBuilding ? "No building now" : "There's a building";
    if (k === "condo") return condo ? "Not a condo" : "It's a condo";
    return "Other";
  });
}

/** What Accept applies by default: the reporter's story count, no building for "no building now", else stories for the
 * reviewer to type (floor area: a direction alone can't make a number), or nothing for a condo or "other" report. */
export function defaultApply(r: Pick<AdminCorrection, "kinds" | "stories">): { apply: "stories" | "empty" | "none"; stories: string } {
  if (r.kinds.includes("stories") && r.stories) return { apply: "stories", stories: String(r.stories) };
  if (r.kinds.includes("gone")) return { apply: "empty", stories: "" };
  if (r.kinds.includes("area")) return { apply: "stories", stories: "" };
  return { apply: "none", stories: "" };
}

export function CorrectionsSection() {
  const [tab, setTab] = useState<CorrectionStatus>("new");
  const [data, setData] = useState<{ reports: AdminCorrection[]; total: number } | null | "failed">(null);
  const [exported, setExported] = useState<AdminCorrectionExport | null | "failed">(null);
  const load = useCallback(() => {
    setData(null);
    fetchAdminCorrections(tab).then((d) => setData(d ?? "failed"));
  }, [tab]);
  useEffect(load, [load]);

  return (
    <div className="flex flex-col gap-3" data-testid="corrections-section">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div role="tablist" aria-label="Reports" className="inline-flex rounded-lg bg-nx-ink/5 p-1">
          {TABS.map(([s, label]) => (
            <button key={s} role="tab" aria-selected={tab === s} onClick={() => setTab(s)}
              className={`rounded-md px-3 py-1 text-caption ${tab === s ? "bg-nx-page font-semibold shadow-sm" : "nx-muted hover:text-nx-ink"}`}>
              {label}{tab === s && data && data !== "failed" ? ` · ${data.total}` : ""}
            </button>
          ))}
        </div>
        <button type="button" className={buttonCls} onClick={() => exportAdminCorrections().then((e) => setExported(e ?? "failed"))} data-testid="corrections-export">
          <FileDiff aria-hidden className="h-4 w-4" strokeWidth={STROKE} />Export accepted
        </button>
      </div>
      {exported && <ExportPanel exported={exported} onClose={() => setExported(null)} />}
      {data === null && <p className="text-caption nx-muted">Loading reports…</p>}
      {data === "failed" && <p className="text-caption text-nx-pill-red">Couldn't load the reports.</p>}
      {data && data !== "failed" && data.reports.length === 0 && (
        <p className="text-caption nx-muted">{tab === "new" ? "No open reports." : "None yet."}</p>
      )}
      {data && data !== "failed" && (
        <ul className="grid gap-3 lg:grid-cols-2">
          {data.reports.map((r) => <ReportCard key={r.id} report={r} onReviewed={load} />)}
        </ul>
      )}
    </div>
  );
}

function ReportCard({ report: r, onReviewed }: { report: AdminCorrection; onReviewed: () => void }) {
  const lat = r.now?.lat, lon = r.now?.lon;
  return (
    <li className="overflow-hidden rounded-xl border border-nx-ink/10 bg-nx-page" data-testid="correction-report">
      <BlockSlice pin10={r.pin10} zoneTag={r.now?.zone_class ?? null} family={familyOf(r.now?.zone_class)} className="h-24" />
      <div className="flex flex-col gap-2 p-3 text-caption">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-body font-semibold">{r.now?.address ? (r.now.address.startsWith("~") ? `Near ${titleCaseAddress(r.now.address.slice(1))}` : titleCaseAddress(r.now.address)) : `PIN ${r.pin10}`}</p>
            <p className="nx-muted">#{r.id} · PIN {r.pin10} · sent {when(r.created_at)}</p>
          </div>
          {lat != null && lon != null && (
            <div className="flex gap-1.5">
              <a href={streetViewUrl(lat, lon)} target="_blank" rel="noopener noreferrer" className={buttonCls}>
                <PersonStanding aria-hidden className="h-4 w-4" strokeWidth={STROKE} />Street View<span className="sr-only"> (opens in a new tab)</span>
              </a>
              <a href={googleMapsUrl(lat, lon)} target="_blank" rel="noopener noreferrer" className={buttonCls}>
                <MapPinned aria-hidden className="h-4 w-4" strokeWidth={STROKE} />Map<span className="sr-only"> (opens in a new tab)</span>
              </a>
            </div>
          )}
        </div>
        <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1">
          <dt className="nx-muted">Card showed</dt>
          <dd>{sqft(r.shown.bldg_sqft)} built{r.shown.bldg_sqft_source ? ` (${SOURCE_WORDS[r.shown.bldg_sqft_source] ?? r.shown.bldg_sqft_source})` : ""} · room {sqft(r.shown.room_sqft)}</dd>
          {r.changed && r.now && (
            <>
              <dt className="nx-muted">Shows now</dt>
              <dd className="text-nx-pill-yellow" data-testid="correction-changed">{sqft(r.now.bldg_sqft)} built ({SOURCE_WORDS[r.now.bldg_sqft_source ?? ""] ?? r.now.bldg_sqft_source ?? "no source"})</dd>
            </>
          )}
          <dt className="nx-muted">Reporter says</dt>
          <dd className="flex flex-wrap gap-1">{reportWords(r).map((w) => <span key={w} className={`${pill} bg-nx-ink/5`}>{w}</span>)}</dd>
          {r.note && (<><dt className="nx-muted">Note</dt><dd className="[overflow-wrap:anywhere]">“{r.note}”</dd></>)}
          <dt className="nx-muted">Reporter</dt>
          <dd className="flex flex-wrap items-center gap-1.5">
            {r.signed_in
              ? <span className={`${pill} bg-nx-pill-green/10 text-nx-pill-green`}><UserRound aria-hidden className="h-3 w-3" strokeWidth={STROKE} />Signed in</span>
              : <span className={`${pill} bg-nx-ink/5`}><UserRoundX aria-hidden className="h-3 w-3" strokeWidth={STROKE} />Signed out</span>}
            <span className="nx-muted">{r.past.accepted} accepted · {r.past.rejected} rejected before</span>
            {r.muted && <span className={`${pill} bg-nx-pill-yellow/10 text-nx-pill-yellow`}>Muted (sorted last)</span>}
          </dd>
          {r.others_open.length > 0 && (<><dt className="nx-muted">Also open</dt><dd>{r.others_open.map((i) => `#${i}`).join(", ")}</dd></>)}
          {r.status !== "new" && (
            <>
              <dt className="nx-muted">Review</dt>
              <dd>{r.status}{r.reviewed_at ? ` ${when(r.reviewed_at)}` : ""}{r.applied ? ` · ${appliedWords(r.applied)}` : ""}{r.review_note ? ` · “${r.review_note}”` : ""}</dd>
            </>
          )}
        </dl>
        {r.status === "new" && <ReviewActions report={r} onReviewed={onReviewed} />}
      </div>
    </li>
  );
}

function appliedWords(a: NonNullable<AdminCorrection["applied"]>): string {
  if (a.stories) return `applies ${a.stories} stories`;
  if (a.empty) return "applies no building";
  return "nothing applied (a case for the Assessor)";
}

function ReviewActions({ report: r, onReviewed }: { report: AdminCorrection; onReviewed: () => void }) {
  const [mode, setMode] = useState<AdminCorrectionReview["action"] | null>(null);
  const init = defaultApply(r);
  const [apply, setApply] = useState(init.apply);
  const [stories, setStories] = useState(init.stories);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const storiesOk = /^\d{1,3}$/.test(stories) && Number(stories) >= 1 && Number(stories) <= 150;
  const ready = mode !== "accept" || apply !== "stories" || storiesOk;

  function open(m: AdminCorrectionReview["action"]) {
    setMode(m);
    setError(null);
    setReason(m === "duplicate" && r.others_open.length ? `Duplicate of #${r.others_open[0]}` : "");
  }

  async function save() {
    if (!mode || !ready || busy) return;
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

  if (!mode) {
    return (
      <div className="flex flex-wrap gap-1.5 pt-1">
        <button type="button" className={buttonCls} onClick={() => open("accept")}><Check aria-hidden className="h-4 w-4" strokeWidth={STROKE} />Accept</button>
        <button type="button" className={buttonCls} onClick={() => open("reject")}><X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />Reject</button>
        <button type="button" className={buttonCls} onClick={() => open("duplicate")}><Copy aria-hidden className="h-4 w-4" strokeWidth={STROKE} />Duplicate</button>
      </div>
    );
  }
  return (
    <form className="flex flex-col gap-2 rounded-lg bg-nx-block p-2.5" onSubmit={(e) => { e.preventDefault(); void save(); }} data-testid="correction-review">
      {mode === "accept" && (
        <fieldset className="flex flex-col gap-1.5">
          <legend className="mb-1 font-medium">Apply</legend>
          <label className="flex items-center gap-2">
            <input type="radio" name={`apply-${r.id}`} checked={apply === "stories"} onChange={() => setApply("stories")} />
            Stories I see
            <input type="text" inputMode="numeric" maxLength={3} value={stories} aria-label="Stories to apply" disabled={apply !== "stories"}
              onChange={(e) => setStories(e.target.value.replace(/\D/g, ""))} className={`${inputCls} w-16 text-center`} />
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name={`apply-${r.id}`} checked={apply === "empty"} onChange={() => setApply("empty")} />No building
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name={`apply-${r.id}`} checked={apply === "none"} onChange={() => setApply("none")} />Nothing: a case for the Assessor
          </label>
          <p className="nx-muted">Applies only over the footprint estimate; a government record always wins.</p>
        </fieldset>
      )}
      <input type="text" maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)}
        placeholder={mode === "reject" ? "Why (optional)" : "What you saw (optional)"} aria-label="Reason" className={inputCls} />
      {error && <p role="alert" className="text-nx-pill-red">{error}</p>}
      <div className="flex gap-1.5">
        <button type="submit" disabled={!ready || busy} className={`${buttonCls} bg-nx-ink font-semibold text-nx-on-ink`} data-testid="correction-review-save">
          {mode === "accept" ? "Accept" : mode === "reject" ? "Reject" : "Mark duplicate"}
        </button>
        <button type="button" className={buttonCls} onClick={() => setMode(null)}>Cancel</button>
      </div>
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
