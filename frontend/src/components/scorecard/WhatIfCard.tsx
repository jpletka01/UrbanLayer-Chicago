// WhatIfCard — "What if this were rezoned?" (WS5 PR2, decision Item 43). For small developers who are not very
// tech savvy: one plain question, a short choice list of the plausible next districts (plus "any district"), and
// a two-column comparison of what each district's table allows on THIS lot. Arithmetic, not a forecast: the copy
// says a rezoning needs City Council approval and names what the table cannot know. Never "you can build".
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { fetchWhatIf, type WhatIfFigures, type WhatIfResponse } from "../../lib/api";

interface WhatIfCardProps {
  currentDistrict: string;
  lotSqft?: number | null;
  /** RS-3 only: the parcel's 606 status from the Profile's unit yield (true / false / unknown). */
  in606?: boolean | null;
}

type Load = { status: "idle" | "loading" | "failed" } | { status: "ready"; data: WhatIfResponse };

export function WhatIfCard({ currentDistrict, lotSqft, in606 }: WhatIfCardProps) {
  const { t, i18n } = useTranslation("pages");
  const [lists, setLists] = useState<WhatIfResponse | null>(null);
  const [choice, setChoice] = useState<string | null>(null);
  const [load, setLoad] = useState<Load>({ status: "idle" });

  useEffect(() => {
    let cancelled = false;
    fetchWhatIf(currentDistrict).then((d) => { if (!cancelled) setLists(d); });
    return () => { cancelled = true; };
  }, [currentDistrict]);

  const pick = (district: string) => {
    if (!district) return;
    setChoice(district);
    setLoad({ status: "loading" });
    fetchWhatIf(currentDistrict, district, lotSqft, in606).then((d) => setLoad(d ? { status: "ready", data: d } : { status: "failed" }));
  };

  if (!lists) return null;
  const others = lists.districts.filter((d) => d !== currentDistrict);
  const nf = new Intl.NumberFormat(i18n.language === "es" ? "es-MX" : "en-US");
  const data = load.status === "ready" ? load.data : null;

  return (
    <section className="space-y-4 mt-8 max-w-3xl" data-testid="what-if">
      <div>
        <h3 className="text-title text-text-primary">{t("scorecard.whatIf.title")}</h3>
        <p className="text-caption text-text-secondary mt-1">{t("scorecard.whatIf.intro", { district: currentDistrict })}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t("scorecard.whatIf.choose")}>
        {lists.suggestions.map((d) => (
          <button
            key={d}
            type="button"
            aria-pressed={choice === d}
            onClick={() => pick(d)}
            className={`touch-target rounded-md border px-3 py-1.5 text-caption font-mono transition-colors ${choice === d ? "border-action text-text-primary bg-dark-elevated" : "border-dark-border text-text-secondary hover:border-action"}`}
          >
            {d}
          </button>
        ))}
        <label className="text-caption text-text-secondary flex items-center gap-2">
          <span className="sr-only">{t("scorecard.whatIf.any")}</span>
          <select
            className="touch-field rounded-lg border border-dark-border bg-dark-surface px-2 py-1.5 text-caption text-text-primary"
            value={choice && !lists.suggestions.includes(choice) ? choice : ""}
            onChange={(e) => pick(e.target.value)}
            data-testid="what-if-any"
          >
            <option value="">{t("scorecard.whatIf.any")}</option>
            {others.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
      </div>
      {load.status === "loading" && <p className="text-caption text-text-muted">{t("scorecard.whatIf.loading")}</p>}
      {load.status === "failed" && <p role="status" className="text-caption text-text-secondary">{t("scorecard.whatIf.failed")}</p>}
      {data?.target && <Comparison current={data.current ?? null} target={data.target} currentLabel={currentDistrict} lot={data.lot_sqft ?? null} nf={nf} />}
      <p className="text-micro text-text-muted leading-relaxed">{t("scorecard.whatIf.note")}</p>
    </section>
  );
}

function Comparison({ current, target, currentLabel, lot, nf }: {
  current: WhatIfFigures | null; target: WhatIfFigures; currentLabel: string; lot: number | null; nf: Intl.NumberFormat;
}) {
  const { t } = useTranslation("pages");
  const dash = "—";
  const rows: Array<{ key: string; label: string; get: (f: WhatIfFigures) => string }> = [
    { key: "far", label: t("scorecard.whatIf.row.far"), get: (f) => (f.far != null ? String(f.far) : t("scorecard.whatIf.noFar")) },
    { key: "floor", label: t("scorecard.whatIf.row.floorArea"), get: (f) => (f.max_floor_area_sqft != null ? t("scorecard.whatIf.sqft", { n: nf.format(f.max_floor_area_sqft) }) : dash) },
    { key: "height", label: t("scorecard.whatIf.row.height"), get: (f) => f.max_height ?? dash },
    { key: "units", label: t("scorecard.whatIf.row.units"), get: (f) => (f.units_by_lot_area != null ? nf.format(f.units_by_lot_area) : t("scorecard.whatIf.noUnits")) },
    { key: "code", label: t("scorecard.whatIf.row.code"), get: (f) => f.code_section },
  ];
  return (
    <div className="overflow-x-auto" data-testid="what-if-table">
      <table className="w-full text-caption">
        <thead>
          <tr className="text-text-muted">
            <th className="text-left font-normal py-1 pr-3" scope="col"><span className="sr-only">{t("scorecard.whatIf.row.label")}</span></th>
            <th className="text-left font-normal py-1 pr-3 font-mono" scope="col">{t("scorecard.whatIf.today", { district: currentLabel })}</th>
            <th className="text-left font-normal py-1 font-mono" scope="col">{t("scorecard.whatIf.if", { district: target.zone_class })}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-t border-dark-border">
              <th scope="row" className="text-left font-normal text-text-secondary py-1.5 pr-3">{r.label}</th>
              <td className="py-1.5 pr-3 text-text-primary">{current ? r.get(current) : t("scorecard.whatIf.pdCurrent")}</td>
              <td className="py-1.5 text-text-primary">{r.get(target)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {lot == null && <p className="text-micro text-text-muted mt-1">{t("scorecard.whatIf.noLot")}</p>}
    </div>
  );
}
