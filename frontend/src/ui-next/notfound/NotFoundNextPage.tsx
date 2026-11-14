// The 404 page in the new UI (Phase 10): an unknown address still gets the frame, so the side panel is there, and two
// ways on: look up a lot, or open Discovery.
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AppFrame } from "../frame/AppFrame";
import { ICON, STROKE } from "../icons";

export default function NotFoundNextPage() {
  const { t } = useTranslation("next");
  const Search = ICON.search;
  const Discovery = ICON.discovery;
  const btn = "inline-flex items-center gap-2 rounded-full px-4 py-2.5 font-semibold touch-target";
  return (
    <AppFrame crumbs={[t("notFound.crumb")]}>
      <div className="mx-auto flex max-w-[60ch] flex-col items-center gap-3 px-4 py-24 text-center" data-testid="not-found">
        <p className="text-caption font-medium nx-muted">404</p>
        <h1 className="text-[1.875rem] font-semibold tracking-[-0.02em]">{t("notFound.title")}</h1>
        <p className="nx-muted [text-wrap:balance]">{t("notFound.body")}</p>
        <div className="mt-4 flex flex-wrap justify-center gap-3">
          <Link to="/scorecard" className={`${btn} bg-nx-primary text-nx-primary-fg`}>
            <Search aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("notFound.lookup")}
          </Link>
          <Link to="/discovery" className={`${btn} ring-1 ring-inset ring-nx-ink/20 hover:bg-nx-ink/5`}>
            <Discovery aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("notFound.discover")}
          </Link>
        </div>
      </div>
    </AppFrame>
  );
}
