// A Chicago Landmark designation Council has passed that the City's landmark map doesn't show for this parcel yet
// (WS1 M5b). Says what the ordinance lists ("listing this address"), never that the parcel IS a landmark; for a
// district it names the blocks and says the boundary is in the ordinance. When the landmark layers didn't answer
// it does not claim the map says no.
import { useTranslation } from "react-i18next";
import { formatDay } from "../../lib/format";
import type { PassedLandmarkDesignation } from "../../lib/types";

export function LandmarkDesignationBox({ hits }: { hits: PassedLandmarkDesignation[] | null | undefined }) {
  const { t } = useTranslation("pages");
  if (!hits || hits.length === 0) return null;
  return (
    <div className="space-y-2" data-testid="landmark-designation-passed">
      {hits.map((h) => {
        const named = h.name && h.name.toLowerCase() !== "building" ? `${h.name} (${h.record})` : h.record;
        const date = formatDay(h.passed_on);
        return (
          <div key={h.record} className="rounded-lg border border-state-warning/40 bg-state-warning/10 px-3 py-2.5">
            <div className="text-body text-text-primary leading-snug">{t("scorecard.landmarkDesignation.title")}</div>
            <p className="text-caption text-text-secondary mt-0.5 leading-snug">
              {h.kind === "district"
                ? t("scorecard.landmarkDesignation.district", { what: named, date, segment: h.segment ?? "" })
                : t("scorecard.landmarkDesignation.building", { what: named, date })}
              {" "}
              {h.map_checked ? t("scorecard.landmarkDesignation.mapChecked") : t("scorecard.landmarkDesignation.mapUnchecked")}
              {" "}
              {t("scorecard.landmarkDesignation.review")}
              {" "}
              <a href={h.url} target="_blank" rel="noopener noreferrer" className="underline">{h.record} ↗</a>
            </p>
          </div>
        );
      })}
    </div>
  );
}
