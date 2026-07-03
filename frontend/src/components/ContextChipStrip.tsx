import { useTranslation } from "react-i18next";
import type { ContextObject, MapData, SidebarView } from "../lib/types";
import { hasSpatialMapContent } from "../lib/mapColors";
import { countDataCategories } from "../lib/contextSummary";

interface Props {
  context: ContextObject | null;
  mapData: MapData | null;
  /** Open the side panel / mobile sheet on the given tab, scoped to this message's turn. */
  onOpen: (tab: SidebarView) => void;
}

const CHIP =
  "flex items-center gap-1.5 px-2.5 py-1 text-caption text-text-secondary border border-dark-border " +
  "rounded-md hover:text-text-primary hover:border-accent/60 transition-colors";

/**
 * Per-message context chips under a completed assistant answer: what this turn
 * produced (map points / data cards / code sources) and a one-tap door to it.
 * Makes the per-message context model visible — without these, data arrives
 * silently in the side panel (desktop) or behind a nav icon (mobile).
 */
export function ContextChipStrip({ context, mapData, onOpen }: Props) {
  const { t } = useTranslation("chat");

  const points = mapData
    ? mapData.crimes.length + mapData.requests_311.length + mapData.building_permits.length
    : 0;
  const showMap = hasSpatialMapContent(
    mapData,
    !!context?.neighborhood?.transit,
    context?.property?.parcel_geometry,
  );
  const dataCount = countDataCategories(context);
  const sourceCount = context?.code_chunks?.length ?? 0;

  if (!showMap && dataCount === 0 && sourceCount === 0) return null;

  return (
    <div className="mt-2 pl-9 flex flex-wrap gap-1.5">
      {showMap && (
        <button type="button" className={CHIP} onClick={() => onOpen("map")}>
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
          </svg>
          {points > 0 ? t("chips.mapCount", { count: points }) : t("chips.map")}
        </button>
      )}
      {dataCount > 0 && (
        <button type="button" className={CHIP} onClick={() => onOpen("data")}>
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
          </svg>
          {t("chips.data", { count: dataCount })}
        </button>
      )}
      {sourceCount > 0 && (
        <button type="button" className={CHIP} onClick={() => onOpen("sources")}>
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
          </svg>
          {t("chips.sources", { count: sourceCount })}
        </button>
      )}
    </div>
  );
}
