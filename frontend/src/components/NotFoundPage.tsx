import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import PageHeader from "./PageHeader";

// Catch-all route. Without it, unknown paths rendered a blank page with no
// navigation (React Router matched nothing).
export function NotFoundPage() {
  const { t } = useTranslation("pages");
  return (
    <div className="min-h-screen bg-dark-bg text-text-primary">
      <PageHeader />
      <main className="max-w-xl mx-auto px-6 py-24 text-center">
        <p className="text-overline text-text-muted mb-3">404</p>
        <h1 className="text-section font-semibold tracking-tight mb-4">{t("notFound.title")}</h1>
        <p className="text-text-secondary mb-8">{t("notFound.body")}</p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link
            to="/"
            className="rounded-lg bg-action hover:bg-action-hover px-5 py-2.5 text-body font-medium text-text-on-accent"
          >
            {t("notFound.lookup")}
          </Link>
          <Link
            to="/discovery"
            className="rounded-lg border border-dark-border px-5 py-2.5 text-body font-medium text-link hover:border-dark-border-strong"
          >
            {t("notFound.discover")}
          </Link>
        </div>
      </main>
    </div>
  );
}
