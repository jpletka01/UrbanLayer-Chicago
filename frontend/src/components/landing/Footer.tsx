import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import ThemeToggle from "../ThemeToggle";

export function Footer() {
  const { t } = useTranslation("landing");
  // Bento near-black footer band with a faint orange top bloom. data-theme="dark" keeps it a
  // mode-locked dark island (dark grounding band under the near-white light theme too).
  return (
    <footer data-theme="dark" className="relative bg-dark-bg border-t border-dark-border overflow-hidden">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-28 left-1/2 -translate-x-1/2 w-[640px] h-48 rounded-full"
        style={{ background: "radial-gradient(circle, rgba(249,164,116,0.10), transparent 70%)", filter: "blur(70px)" }}
      />
      <div className="relative max-w-6xl mx-auto py-14 px-6 grid grid-cols-1 md:grid-cols-3 gap-10 text-sm">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <img src="/logo.jpg" alt="" className="w-7 h-7 rounded-full" />
            <h4 className="font-display text-text-primary font-semibold text-base tracking-tight">UrbanLayer</h4>
          </div>
          <p className="text-text-secondary leading-relaxed">
            {t("footer.tagline")}
          </p>
          <p className="text-text-muted text-xs">{t("footer.copyright")}</p>
          {/* The anonymous escape hatch: theme control otherwise lives on the
              auth-gated /settings page. The footer is a mode-locked dark island,
              so the toggle renders dark here in both modes — intended. */}
          <ThemeToggle />
        </div>

        <div className="space-y-3">
          <h4 className="text-text-primary font-semibold text-base">{t("footer.dataSources")}</h4>
          <ul className="space-y-2 text-text-secondary text-xs">
            <li>
              <span className="text-text-muted font-medium uppercase tracking-wider">{t("footer.cityOfChicago")}</span>
              <span className="text-text-muted"> — {t("footer.cityOfChicagoDesc")} </span>
              <a href="https://gisapps.chicago.gov/ZoningMapWeb/?liab=1&config=zoning" target="_blank" rel="noopener noreferrer" className="hover:text-accent transition-colors text-text-secondary">
                {t("footer.zoningMapServer")}
              </a>
              <span className="text-text-muted"> {t("footer.overlayLayers")}</span>
            </li>
            <li>
              <span className="text-text-muted font-medium uppercase tracking-wider">{t("footer.cookCounty")}</span>
              <span className="text-text-muted"> — {t("footer.cookCountyDesc")}</span>
            </li>
            <li>
              <span className="text-text-muted font-medium uppercase tracking-wider">{t("footer.federalExternal")}</span>
              <span className="text-text-muted"> — {t("footer.federalExternalDesc")}</span>
            </li>
            <li>
              <span className="text-text-muted font-medium uppercase tracking-wider">{t("footer.legal")}</span>
              <span className="text-text-muted"> — {t("footer.legalDesc")}</span>
            </li>
          </ul>
        </div>

        <div className="space-y-3">
          <h4 className="text-text-primary font-semibold text-base">{t("footer.about")}</h4>
          <ul className="space-y-2 text-text-secondary">
            <li>
              {/* Same-page scroll to the How-it-works section (the /about route
                  is no longer a customer-facing destination). */}
              <a
                href="#how-it-works"
                onClick={(e) => {
                  e.preventDefault();
                  document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" });
                }}
                className="hover:text-accent transition-colors"
              >
                {t("footer.howItWorks")}
              </a>
            </li>
            <li>
              <Link to="/pricing" className="hover:text-accent transition-colors">
                {t("footer.pricing")}
              </Link>
            </li>
            <li>
              <Link to="/privacy" className="hover:text-accent transition-colors">
                {t("footer.privacy")}
              </Link>
            </li>
            <li className="text-text-muted text-xs">{t("footer.notAffiliated")}</li>
            <li className="text-text-muted text-xs">{t("footer.dataDelay")}</li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
