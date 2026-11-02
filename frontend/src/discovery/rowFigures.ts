// A Discovery row's title and figures (decision Items 46, 57), shared by the result list and the dot preview.
import { titleCaseAddress } from "../lib/format";
import type { ResultRow } from "./types";

type TFn = (key: string, opts?: Record<string, unknown>) => string;

function fmtMoney(n: number | null): string | null {
  return n == null ? null : `$${Math.round(n).toLocaleString()}`;
}

function fmtNum(n: number | null): string | null {
  return n == null ? null : Math.round(n).toLocaleString();
}

/** The row's address, title-cased; a "~" prefix (nearest address on record) becomes an "Approx." label. */
export function rowTitle(row: ResultRow): { title: string; approx: boolean } {
  if (!row.address) return { title: row.pin, approx: false };
  const approx = row.address.startsWith("~");
  return { title: titleCaseAddress(approx ? row.address.slice(1) : row.address), approx };
}

/** The row's figures: what the list is sorted by first (the reason for its position), else $/ft², then the
    assessed value. A nominal ($1) assessment reads "Nominal", never "$1" (decision Items 46, 57); $0 stays
    "$0" and a missing value stays missing. */
export function rowFigures(row: ResultRow, activeSortKey: string, t: TFn) {
  const nominal = row.nominal_assessment === true;
  const assessed = nominal ? t("discovery.nominal") : fmtMoney(row.assessed_value);
  const ppsf = !nominal && row.price_per_sf != null ? t("discovery.perSqft", { money: fmtMoney(row.price_per_sf) }) : null;
  const sortValueByKey: Record<string, string | null> = {
    assessed_value: assessed,
    price_per_sf: ppsf,
    lot_size: row.lot_sqft != null ? t("discovery.lot", { n: fmtNum(row.lot_sqft) }) : null,
    building_size: row.bldg_sqft != null ? t("discovery.bldg", { n: fmtNum(row.bldg_sqft) }) : null,
    year_built: row.year_built != null ? String(row.year_built) : null,
  };
  const sortValue = sortValueByKey[activeSortKey] ?? null;
  const primary = sortValue ?? ppsf ?? assessed;
  const primaryLabel = sortValue != null
    ? t(`discovery.sort.${activeSortKey}`, { defaultValue: activeSortKey.replace(/_/g, " ") })
    : primary === ppsf && ppsf != null
      ? t("discovery.metricPerSqft")
      : t("discovery.metricAssessed");
  const secondary =
    assessed && primary !== assessed
      ? nominal ? t("discovery.nominalAv") : t("discovery.av", { money: assessed })
      : ppsf && primary !== ppsf
        ? ppsf
        : null;
  return { primary, primaryLabel, secondary, sortKeyShown: sortValue != null ? activeSortKey : null };
}
