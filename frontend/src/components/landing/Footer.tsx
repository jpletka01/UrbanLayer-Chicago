import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

export function Footer() {
  const { t } = useTranslation("landing");
  // Deep blueprint-navy footer band. data-theme="dark" keeps the text tokens light so they
  // stay readable on the blue in BOTH app themes (a deliberate fixed-blue footer).
  return (
    <footer data-theme="dark" className="bg-[#16284a] border-t border-white/10">
      <div className="max-w-5xl mx-auto py-12 px-6 grid grid-cols-1 md:grid-cols-3 gap-10 text-sm">
        <div className="space-y-3">
          <h4 className="text-text-primary font-semibold text-base">UrbanLayer</h4>
          <p className="text-text-secondary leading-relaxed">
            {t("footer.tagline")}
          </p>
          <p className="text-text-muted text-xs">{t("footer.copyright")}</p>
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
            <li className="text-text-muted text-xs">{t("footer.notAffiliated")}</li>
            <li className="text-text-muted text-xs">{t("footer.dataDelay")}</li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
