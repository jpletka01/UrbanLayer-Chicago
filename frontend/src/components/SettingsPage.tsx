// Settings — account chrome for signed-in users (/settings, ProtectedRoute).
// Account identity is Google's (read-only here); theme/language controls are the
// same components as the headers; billing links out to the Stripe portal and
// lists purchased reports for re-download. Deletion is the page's only
// destructive action — typed confirmation, Stripe-cancel-first on the backend.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuthContext } from "../contexts/AuthContext";
import {
  createBillingPortal,
  deleteAccount,
  fetchMyPurchases,
  fetchReport,
  type ReportPurchase,
} from "../lib/api";
import { buildFilenameSlug } from "../lib/csvExport";
import { formatDate } from "../lib/format";
import PageHeader from "./PageHeader";
import { Card } from "./ui/Card";
import { Chip } from "./ui/Chip";
import { Modal } from "./ui/Modal";
import ThemeToggle from "./ThemeToggle";
import LanguageSelector from "./LanguageSelector";

function SettingsRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <span className="text-body text-text-secondary">{label}</span>
      {children}
    </div>
  );
}

function PurchaseRow({ purchase }: { purchase: ReportPurchase }) {
  const { t } = useTranslation("pages");
  const [downloading, setDownloading] = useState(false);
  const [failed, setFailed] = useState(false);

  async function handleDownload() {
    setDownloading(true);
    setFailed(false);
    const blob = await fetchReport({
      pin: purchase.pin,
      confidence: purchase.pin ? "authoritative" : "approximate",
      lat: purchase.lat,
      lon: purchase.lon,
      address: purchase.address,
    });
    setDownloading(false);
    if (!blob) {
      setFailed(true);
      return;
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${buildFilenameSlug(purchase.address ?? purchase.pin ?? "report")}_feasibility_report.pdf`;
    a.click();
    URL.revokeObjectURL(url);
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
      </div>
      <button
        onClick={handleDownload}
        disabled={downloading}
        className="shrink-0 px-2.5 py-1 rounded-md border border-dark-border text-caption text-text-secondary hover:text-accent hover:border-accent/40 transition-colors disabled:opacity-50"
      >
        {downloading ? t("settings.downloading") : t("settings.download")}
      </button>
    </div>
  );
}

function DeleteAccountModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("pages");
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirmWord = t("settings.deleteConfirmWord");
  const armed = confirmText.trim().toLowerCase() === confirmWord.toLowerCase();

  async function handleDelete() {
    setDeleting(true);
    setError(null);
    try {
      await deleteAccount();
      // Cookies are cleared server-side; a full reload resets all client state.
      window.location.href = "/";
    } catch (err) {
      setDeleting(false);
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <Modal
      onClose={onClose}
      title={t("settings.deleteModalTitle")}
      description={t("settings.deleteModalBody")}
    >
      <label className="block text-caption text-text-secondary mb-1.5">
        {t("settings.deleteConfirmLabel", { word: confirmWord })}
      </label>
      <input
        type="text"
        value={confirmText}
        onChange={(e) => setConfirmText(e.target.value)}
        autoFocus
        className="w-full px-3 py-2 rounded-lg bg-dark-elevated border border-dark-border text-body text-text-primary focus:outline-none focus:border-state-negative/60"
      />
      {error && <p className="mt-2 text-caption text-state-negative">{error}</p>}
      <div className="mt-5 flex justify-end gap-2">
        <button
          onClick={onClose}
          className="px-3 py-2 rounded-lg text-body text-text-secondary hover:text-text-primary transition-colors"
        >
          {t("settings.cancel")}
        </button>
        <button
          onClick={handleDelete}
          disabled={!armed || deleting}
          className="px-3 py-2 rounded-lg bg-state-negative/15 text-state-negative text-body font-medium hover:bg-state-negative/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {deleting ? t("settings.deleting") : t("settings.deleteConfirm")}
        </button>
      </div>
    </Modal>
  );
}

export default function SettingsPage() {
  const { t } = useTranslation("pages");
  const { user, authRequired } = useAuthContext();
  const [purchases, setPurchases] = useState<ReportPurchase[] | null>(null);
  const [portalBusy, setPortalBusy] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    fetchMyPurchases().then(setPurchases).catch(() => setPurchases([]));
  }, []);

  if (!user) return null; // ProtectedRoute redirects; this is a type guard.

  const isPro = user.tier === "premium" || user.tier === "admin";
  const planLabel =
    user.tier === "admin"
      ? t("settings.planAdmin")
      : isPro
        ? t("settings.planPro")
        : t("settings.planFree");

  async function handleManageSubscription() {
    setPortalBusy(true);
    try {
      const { url } = await createBillingPortal();
      window.location.href = url;
    } catch {
      setPortalBusy(false);
      window.location.href = "/pricing";
    }
  }

  return (
    <div className="min-h-screen bg-dark-bg text-text-primary">
      <PageHeader />

      <main className="max-w-2xl mx-auto px-6 py-16 space-y-6">
        <h1 className="text-section mb-2">{t("settings.title")}</h1>

        <Card title={t("settings.account")} padding="lg">
          <div className="flex items-center gap-4">
            {user.picture_url ? (
              <img
                src={user.picture_url}
                alt=""
                className="w-12 h-12 rounded-full"
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="w-12 h-12 rounded-full bg-accent/80 flex items-center justify-center text-subtitle font-medium text-text-on-accent">
                {(user.name || user.email)[0]?.toUpperCase() ?? "?"}
              </div>
            )}
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-title text-text-primary truncate">{user.name}</p>
                {isPro && <Chip tone="accent" size="sm">Pro</Chip>}
              </div>
              <p className="text-body text-text-muted truncate">{user.email}</p>
              <p className="text-caption text-text-muted mt-0.5">
                {t("settings.signedInWith")}
              </p>
            </div>
          </div>
        </Card>

        <Card title={t("settings.appearance")} padding="lg">
          <div className="divide-y divide-dark-border">
            <SettingsRow label={t("settings.theme")}>
              <ThemeToggle />
            </SettingsRow>
            <SettingsRow label={t("settings.language")}>
              <LanguageSelector />
            </SettingsRow>
          </div>
        </Card>

        <Card title={t("settings.billing")} padding="lg">
          <SettingsRow label={t("settings.currentPlan")}>
            <div className="flex items-center gap-3">
              <span className="text-body text-text-primary font-medium">{planLabel}</span>
              {isPro ? (
                <button
                  onClick={handleManageSubscription}
                  disabled={portalBusy}
                  className="px-2.5 py-1 rounded-md bg-highlight-fill text-highlight-fg text-caption hover:opacity-90 transition-opacity disabled:opacity-50"
                >
                  {t("settings.manageSubscription")}
                </button>
              ) : (
                <Link
                  to="/pricing"
                  className="px-2.5 py-1 rounded-md bg-highlight-fill text-highlight-fg text-caption hover:opacity-90 transition-opacity"
                >
                  {t("settings.upgradeToPro")}
                </Link>
              )}
            </div>
          </SettingsRow>
          <p className="text-caption text-text-muted mb-4">
            {isPro ? t("settings.proBlurb") : t("settings.freeBlurb")}
          </p>

          <h3 className="text-caption font-medium text-text-secondary uppercase tracking-wide mb-1">
            {t("settings.purchases")}
          </h3>
          {purchases === null ? (
            <p className="text-caption text-text-muted py-2">…</p>
          ) : purchases.length === 0 ? (
            <p className="text-body text-text-muted py-2">
              {t("settings.purchasesEmpty")}{" "}
              <Link to="/scorecard" className="text-link hover:underline">
                {t("settings.purchasesEmptyCta")}
              </Link>
            </p>
          ) : (
            <div>
              {purchases.map((p) => (
                <PurchaseRow key={p.id} purchase={p} />
              ))}
            </div>
          )}
        </Card>

        {/* Deletion is impossible in dev mode (no real user row) — hide the zone. */}
        {authRequired && (
          <Card title={t("settings.dangerZone")} padding="lg">
            <div className="flex items-center justify-between gap-4">
              <p className="text-body text-text-secondary max-w-sm">
                {t("settings.deleteBlurb")}
              </p>
              <button
                onClick={() => setConfirmingDelete(true)}
                className="shrink-0 px-3 py-2 rounded-lg border border-state-negative/40 text-body text-state-negative hover:bg-state-negative/10 transition-colors"
              >
                {t("settings.deleteAccount")}
              </button>
            </div>
          </Card>
        )}
      </main>

      {confirmingDelete && <DeleteAccountModal onClose={() => setConfirmingDelete(false)} />}
    </div>
  );
}
