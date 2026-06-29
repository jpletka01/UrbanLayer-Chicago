import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { TrendRow } from "../../lib/analytics";
import { capLabel } from "../../lib/mapColors";

type SortKey = "category" | "current" | "prior" | "change";
type SortDir = "asc" | "desc";

interface Props {
  rows: TrendRow[];
  currentLabel: string;
  priorLabel: string;
}


export function TrendTable({ rows, currentLabel, priorLabel }: Props) {
  const { t } = useTranslation("data");
  const [sortKey, setSortKey] = useState<SortKey>("current");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  if (rows.length === 0) return null;

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(d => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const sorted = [...rows].sort((a, b) => {
    let cmp = 0;
    switch (sortKey) {
      case "category": cmp = a.category.localeCompare(b.category); break;
      case "current": cmp = a.currentCount - b.currentCount; break;
      case "prior": cmp = a.priorCount - b.priorCount; break;
      case "change": cmp = a.changePercent - b.changePercent; break;
    }
    return sortDir === "asc" ? cmp : -cmp;
  });

  const arrow = (key: SortKey) => {
    if (sortKey !== key) return "";
    return sortDir === "asc" ? " ▲" : " ▼";
  };

  return (
    <div className="w-full">
      <table className="w-full text-micro">
        <thead>
          <tr className="text-text-muted border-b border-dark-border">
            <th
              className="text-left font-medium py-1.5 pr-2 cursor-pointer hover:text-text-secondary"
              onClick={() => toggleSort("category")}
            >
              {t("analytics.type")}{arrow("category")}
            </th>
            <th
              className="text-right font-medium py-1.5 px-1 cursor-pointer hover:text-text-secondary whitespace-nowrap"
              onClick={() => toggleSort("current")}
            >
              {currentLabel}{arrow("current")}
            </th>
            <th
              className="text-right font-medium py-1.5 px-1 cursor-pointer hover:text-text-secondary whitespace-nowrap"
              onClick={() => toggleSort("prior")}
            >
              {priorLabel}{arrow("prior")}
            </th>
            <th
              className="text-right font-medium py-1.5 pl-1 cursor-pointer hover:text-text-secondary"
              onClick={() => toggleSort("change")}
            >
              {t("analytics.trend")}{arrow("change")}
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.category} className="border-b border-dark-border/50">
              <td className="py-1.5 pr-2">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: row.color }}
                  />
                  <span className="text-text-secondary truncate max-w-[100px]">
                    {capLabel(row.category)}
                  </span>
                </div>
              </td>
              <td className="text-right text-text-primary font-mono py-1.5 px-1">
                {row.currentCount}
              </td>
              <td className="text-right text-text-muted font-mono py-1.5 px-1">
                {row.priorCount}
              </td>
              <td className="text-right py-1.5 pl-1">
                <TrendBadge percent={row.changePercent} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TrendBadge({ percent }: { percent: number }) {
  if (percent === 0) {
    return <span className="text-text-muted font-mono">--</span>;
  }

  const isUp = percent > 0;
  const arrow = isUp ? "↑" : "↓";
  const color = isUp ? "text-state-negative" : "text-state-positive";

  return (
    <span className={`font-mono font-medium ${color}`}>
      {arrow}{Math.abs(percent)}%
    </span>
  );
}
