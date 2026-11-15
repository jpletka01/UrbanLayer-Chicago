// The month/year switch Pricing and Settings → Plan share (Item 123).
import { useTranslation } from "react-i18next";
import type { BillingInterval } from "../../lib/api";
import { localeOf } from "./useProCheckout";
import { PRICE_CENTS, dollars, yearlySavingsCents } from "./pricingModel";

/** Monthly / Yearly as a radio group; "Save $29" rides the yearly choice. `prices` puts the price in each label. */
export function IntervalSwitch({ value, onChange, prices = false, idPrefix }: {
  value: BillingInterval;
  onChange: (v: BillingInterval) => void;
  prices?: boolean;
  idPrefix: string;
}) {
  const { t, i18n } = useTranslation("next");
  const locale = localeOf(i18n.language);
  const options: BillingInterval[] = ["month", "year"];
  return (
    <div role="radiogroup" aria-label={t("pricing.billing")} className="inline-flex flex-wrap self-start rounded-full p-1 ring-1 ring-inset ring-nx-ink/15" data-testid={`${idPrefix}-interval`}>
      {options.map((o) => {
        const on = value === o;
        return (
          <button key={o} type="button" role="radio" aria-checked={on} onClick={() => onChange(o)} data-interval={o}
            className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 touch-target ${on ? "bg-nx-primary font-semibold text-nx-primary-fg" : "hover:bg-nx-ink/5"}`}>
            {prices
              ? t(o === "month" ? "pricing.perMonthPrice" : "pricing.perYearPrice", { price: dollars(PRICE_CENTS[o], locale) })
              : t(o === "month" ? "pricing.monthly" : "pricing.yearly")}
            {o === "year" && (
              <span className={`rounded-lg px-2 py-px text-caption ${on ? "bg-nx-primary-fg/20" : "bg-nx-pill-green-bg text-nx-pill-green"}`}>
                {t("pricing.save", { amount: dollars(yearlySavingsCents(), locale) })}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

