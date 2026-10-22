// One purchased report in Settings (WS6 M8). A purchase keeps the first report it rendered as its original; once
// there is one the row offers it beside an updated copy, and before that a single download, which becomes the
// original.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { fetchReport, type ReportPurchase } from "../../lib/api";
import { buildFilenameSlug } from "../../lib/csvExport";
import { formatDate } from "../../lib/format";
import { describeChange } from "../../lib/sinceThen";

export function PurchaseRow({ purchase, onDownloaded }: { purchase: ReportPurchase; onDownloaded?: () => void }) {
  const { t } = useTranslation("pages");
  const { t: tc } = useTranslation("chat");
  const [downloading, setDownloading] = useState<"original" | "updated" | null>(null);
  const [failed, setFailed] = useState(false);
  const original = purchase.original ?? null;

  async function handleDownload(copy?: "original" | "updated") {
    setDownloading(copy ?? "updated");
    setFailed(false);
    const blob = await fetchReport({
      pin: purchase.pin,
      confidence: purchase.pin ? "authoritative" : "approximate",
      lat: purchase.lat,
      lon: purchase.lon,
      address: purchase.address,
    }, copy);
    setDownloading(null);
    if (!blob) {
      setFailed(true);
      return;
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const slug = buildFilenameSlug(purchase.address ?? purchase.pin ?? "report");
    a.download = `${slug}_feasibility_report${copy === "original" ? "_original" : ""}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
    if (!original) onDownloaded?.(); // that download just became the original: show both buttons now
  }

  const when = purchase.completed_at
    ? formatDate(new Date(purchase.completed_at).toISOString())
    : "";

  return (
    <div className="flex items-center justify-between gap-4 py-2.5 border-b border-dark-border last:border-b-0">
      <div className="min-w-0">
        <p className="text-body text-text-primary truncate">
          {purchase.address ?? purchase.pin}
        </p>
        <p className="text-caption text-text-muted">
          {when} · ${(purchase.amount_cents / 100).toFixed(0)}
          {failed && (
            <span className="text-state-negative ml-2">{t("settings.downloadFailed")}</span>
          )}
        </p>
        {purchase.changes?.status === "changes" && (
          <p className="text-caption text-state-warning" data-testid="purchase-changes">
            {t("settings.sinceReport", { what: purchase.changes.changes.map((c) => describeChange(c, tc).text.replace(/\.$/, "")).join("; ") })}
          </p>
        )}
        {original && (
          <p className="text-caption text-text-muted" data-testid="original-note">
            {original.available ? t("settings.originalNote") : t("settings.originalMissing")}
          </p>
        )}
      </div>
      <div className="shrink-0 flex flex-col items-end gap-1.5 sm:flex-row sm:items-center">
        {original?.available && (
          <button
            onClick={() => handleDownload("original")}
            disabled={downloading !== null}
            data-testid="download-original"
            className="px-2.5 py-1 rounded-md border border-dark-border text-caption text-text-secondary hover:text-accent hover:border-accent/40 transition-colors disabled:opacity-50"
          >
            {downloading === "original"
              ? t("settings.downloading")
              : t("settings.downloadOriginal", { date: formatDate(new Date(original.rendered_at).toISOString()) })}
          </button>
        )}
        <button
          onClick={() => handleDownload(original ? "updated" : undefined)}
          disabled={downloading !== null}
          data-testid="download-updated"
          className="px-2.5 py-1 rounded-md border border-dark-border text-caption text-text-secondary hover:text-accent hover:border-accent/40 transition-colors disabled:opacity-50"
        >
          {downloading === "updated" ? t("settings.downloading") : original ? t("settings.downloadUpdated") : t("settings.download")}
        </button>
      </div>
    </div>
  );
}
