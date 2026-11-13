// Pricing in the new UI (Item 123, owner-approved design board "Pricing and Plan Design", 2026-11-13). Replaces the
// stale $99 page: Free and Pro side by side, $19 a month or $199 a year, the free plan complete (nothing locked or
// blurred), and four plain answers about paying. On a phone Pro comes first, since it carries the one action. While
// purchases are off (production Stripe not set up), Pro says "Coming soon" instead of a button.
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Check, CreditCard, Sparkles } from "lucide-react";
import { useAuthContext } from "../../contexts/AuthContext";
import type { BillingInterval } from "../../lib/api";
import { usePayments } from "../../lib/usePayments";
import { AppFrame } from "../frame/AppFrame";
import { STROKE } from "../icons";
import { Block, Pill } from "../ui/Blocks";
import { IntervalSwitch } from "./ProOffer";
import { localeOf, useProCheckout } from "./useProCheckout";
import { PRICE_CENTS, dollars, yearlyPerMonthCents } from "./pricingModel";

const BTN_PRIMARY = "inline-flex items-center justify-center gap-2 rounded-full bg-nx-primary px-4 py-2 font-semibold text-nx-primary-fg disabled:opacity-50 touch-target";
const BTN_SECONDARY = "inline-flex items-center justify-center gap-2 rounded-full px-3.5 py-2 font-medium ring-1 ring-inset ring-nx-ink/20 hover:bg-nx-ink/5 disabled:opacity-50 touch-target";

function Features({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-col gap-2.5">
      {items.map((f) => (
        <li key={f} className="flex items-start gap-2.5">
          <Check aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-nx-pill-green" strokeWidth={STROKE} />{f}
        </li>
      ))}
    </ul>
  );
}

export default function PricingNextPage() {
  const { t, i18n } = useTranslation("next");
  const locale = localeOf(i18n.language);
  const { user, isAuthenticated, authRequired, signIn } = useAuthContext();
  const payments = usePayments();
  const [interval, setBilling] = useState<BillingInterval>("month");
  const checkout = useProCheckout("pricing");

  const signedIn = isAuthenticated || !authRequired;
  const plan = user?.tier === "admin" ? "admin" : user?.tier === "premium" ? "pro" : "free";
  const purchasesOff = payments?.subscriptions === false;
  const price = dollars(PRICE_CENTS[interval], locale);
  const list = (key: string) => t(key, { returnObjects: true }) as string[];

  let proAction: ReactNode;
  if (plan === "pro") {
    proAction = (
      <Link to="/settings/plan" className={`${BTN_SECONDARY} self-start`}>
        <CreditCard aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("pricing.seeYourPlan")}
      </Link>
    );
  } else if (plan === "admin") {
    proAction = <span className="text-caption nx-muted">{t("pricing.adminNote")}</span>;
  } else if (purchasesOff) {
    proAction = (
      <>
        <span className="self-start"><Pill tone="gray">{t("settings.planSection.comingSoon")}</Pill></span>
        <span className="text-caption nx-muted">{t("pricing.comingSoonNote")}</span>
      </>
    );
  } else if (!signedIn) {
    proAction = (
      <>
        <button type="button" onClick={signIn} className={BTN_PRIMARY} data-testid="pricing-get-pro">{t("pricing.signInForPro")}</button>
        <span className="text-caption nx-muted">{t("pricing.signInNote")}</span>
      </>
    );
  } else {
    proAction = (
      <>
        <button type="button" onClick={() => checkout.start(interval)} disabled={checkout.busy} className={BTN_PRIMARY} data-testid="pricing-get-pro">
          {checkout.busy ? t("pricing.toStripe") : t(interval === "month" ? "pricing.getProMonth" : "pricing.getProYear", { price })}
        </button>
        <span className="text-caption nx-muted">{t("pricing.stripeNote")}</span>
        {checkout.error && <p role="alert" className="rounded-xl bg-nx-pill-red-bg px-4 py-3 text-caption text-nx-pill-red">{t("pricing.checkoutFailed")}</p>}
      </>
    );
  }

  return (
    <AppFrame crumbs={[t("pricing.title")]}>
      <div className="mx-auto flex max-w-[960px] flex-col gap-5 px-4 py-6 sm:px-8 sm:py-10" data-testid="pricing">
        <h1 className="text-[1.875rem] font-semibold tracking-[-0.02em]">{t("pricing.heading")}</h1>
        <p className="-mt-2 max-w-[62ch] nx-muted">{t("pricing.lead")}</p>
        <IntervalSwitch value={interval} onChange={setBilling} idPrefix="pricing" />

        <div className="grid gap-4 md:grid-cols-2">
          <section className="flex min-w-0 flex-col gap-4 rounded-2xl bg-nx-block p-5 sm:p-6" aria-labelledby="pricing-free" data-testid="pricing-free">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="pricing-free" className="text-body font-semibold">{t("pricing.free")}</h2>
              {signedIn && plan === "free" && <Pill tone="gray">{t("pricing.yourPlan")}</Pill>}
            </div>
            <p className="text-[2.25rem] font-semibold leading-none tracking-[-0.02em] tabular-nums">{dollars(0, locale)}</p>
            <Features items={list("pricing.freeFeatures")} />
            <div className="mt-auto flex flex-col gap-2 border-t border-nx-ink/10 pt-4">
              {!signedIn
                ? <button type="button" onClick={signIn} className={`${BTN_SECONDARY} self-start`}>{t("pricing.signInFree")}</button>
                : null}
              <span className="text-caption nx-muted">{t("pricing.signedOutNote")}</span>
            </div>
          </section>

          <section className="order-first flex min-w-0 flex-col gap-4 rounded-2xl bg-nx-block p-5 sm:p-6 md:order-none" aria-labelledby="pricing-pro" data-testid="pricing-pro">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="pricing-pro" className="flex items-center gap-2 text-body font-semibold">
                <Sparkles aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("pricing.pro")}
              </h2>
              {plan === "pro"
                ? <Pill tone="purple">{t("pricing.yourPlan")}</Pill>
                : interval === "year" && <Pill tone="purple">{t("pricing.perMonthBilledYearly", { price: dollars(yearlyPerMonthCents(), locale) })}</Pill>}
            </div>
            <p className="flex flex-wrap items-baseline gap-1.5">
              <span className="text-[2.25rem] font-semibold leading-none tracking-[-0.02em] tabular-nums" data-testid="pricing-price">{price}</span>
              <span className="nx-muted">{t(interval === "month" ? "pricing.aMonth" : "pricing.aYear")}</span>
            </p>
            <Features items={list("pricing.proFeatures")} />
            <div className="mt-auto flex flex-col gap-2 border-t border-nx-ink/10 pt-4">{proAction}</div>
          </section>
        </div>

        <Block title={t("pricing.qaTitle")} labelledBy="pricing-qa">
          <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            {(["cancel", "interval", "trial", "reports"] as const).map((k) => (
              <div key={k} className="flex flex-col gap-1">
                <dt className="font-semibold">{t(`pricing.qa.${k}.q`)}</dt>
                <dd className="nx-muted">{t(`pricing.qa.${k}.a`, {
                  month: dollars(PRICE_CENTS.month, locale), year: dollars(PRICE_CENTS.year, locale),
                })}</dd>
              </div>
            ))}
          </dl>
        </Block>
      </div>
    </AppFrame>
  );
}
