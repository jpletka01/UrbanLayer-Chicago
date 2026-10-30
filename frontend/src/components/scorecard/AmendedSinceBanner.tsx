// The amber banner above a Municipal Code section the text predates a change to, and the
// page that replaces a bare 404 for a section an amendment added (17-3-0600) that the
// published code text does not hold yet. Both say what the text below can't be trusted for
// and link the ordinance; the summary is shown only when someone has read the ordinance.
import { useTranslation } from "react-i18next";
import { formatDay } from "../../lib/format";
import type { SectionNotCodified } from "../../lib/api";
import type { Amendment } from "../../lib/types";
import { RecordLink } from "./AmendmentList";

function Items({ amendments }: { amendments: Amendment[] }) {
  return (
    <ul className="mt-1.5 space-y-1">
      {amendments.map((a) => (
        <li key={a.record} data-testid={`amended-${a.record}`}>
          <RecordLink a={a} />, {formatDay(a.passed_on)}
          {": "}
          {a.summary || a.title}
        </li>
      ))}
    </ul>
  );
}

const boxCls = "rounded-lg border border-state-warning/30 bg-state-warning/10 px-3 py-2.5 text-caption text-text-primary leading-relaxed";

export function AmendedSinceBanner({ amendments }: { amendments?: Amendment[] | null }) {
  const { t } = useTranslation("pages");
  if (!amendments?.length) return null;
  return (
    <div className={boxCls} role="note" data-testid="amended-since">
      <div className="font-medium">{t("scorecard.amendments.banner.title", { count: amendments.length })}</div>
      <Items amendments={amendments} />
      <div className="mt-1.5 text-text-secondary">{t("scorecard.amendments.banner.caveat", { count: amendments.length })}</div>
    </div>
  );
}

export function NotCodifiedNotice({ notice }: { notice: SectionNotCodified }) {
  const { t } = useTranslation("pages");
  return (
    <div className={boxCls} role="note" data-testid="not-codified">
      <div className="font-medium">{t("scorecard.amendments.notCodified.title", { section: notice.section_id })}</div>
      <p className="mt-1">{t("scorecard.amendments.notCodified.body", { section: notice.section_id, count: notice.added_by.length })}</p>
      <Items amendments={notice.added_by} />
    </div>
  );
}
