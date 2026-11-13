// Pricing in the new UI (Item 123). Owner's look, 2026-11-13: three plans side by side under a centered heading
// (Free, Pro monthly, Pro yearly), each with its own price and button, instead of a month/year switch in a corner;
// the Pro cards wear a thin lavender rim with a slow light; no "paid by Stripe" note; the questions as a plain list.
// The free plan is complete (nothing locked or blurred). While purchases are off, Pro says "Coming soon".
// On a phone the Pro cards come first, since they carry the actions.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Check, CreditCard, Sparkles } from "lucide-react";
import { useAuthContext } from "../../contexts/AuthContext";
import type { BillingInterval } from "../../lib/api";
import { usePayments } from "../../lib/usePayments";
import { AppFrame } from "../frame/AppFrame";
import { STROKE } from "../icons";
import { Pill } from "../ui/Blocks";
import { localeOf, useProCheckout } from "./useProCheckout";
import { PRICE_CENTS, dollars, yearlyPerMonthCents, yearlySavingsCents } from "./pricingModel";

const BTN_PRIMARY = "inline-flex w-full items-center justify-center gap-2 rounded-full bg-nx-primary px-4 py-2.5 font-semibold text-nx-primary-fg disabled:opacity-50 touch-target";
const BTN_SECONDARY = "inline-flex w-full items-center justify-center gap-2 rounded-full px-4 py-2.5 font-medium ring-1 ring-inset ring-nx-ink/20 hover:bg-nx-ink/5 disabled:opacity-50 touch-target";

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

/** One plan: name and tag, the price on its own line, a note under it, what it includes, the action at the foot. */
function PlanCard({ id, name, tag, price, per, note, features, action, pro = false, className = "" }: {
  id: string; name: ReactNode; tag?: ReactNode; price: string; per?: string; note?: ReactNode;
  features: string[]; action: ReactNode; pro?: boolean; className?: string;
}) {
  const card = (
    <section className="flex h-full min-w-0 flex-col gap-5 rounded-2xl bg-nx-block p-5 sm:p-6" aria-labelledby={`pricing-${id}-name`} data-testid={`pricing-${id}`}>
      <div className="flex min-h-[1.5rem] flex-wrap items-center justify-between gap-2">
        <h2 id={`pricing-${id}-name`} className="flex items-center gap-2 text-body font-semibold">
          {pro && <Sparkles aria-hidden className="h-4 w-4" strokeWidth={STROKE} />}{name}
        </h2>
        {tag}
      </div>
      <div className="flex flex-col gap-1">
        <p className="flex flex-wrap items-baseline gap-1.5">
          <span className="text-[2.25rem] font-semibold leading-none tracking-[-0.02em] tabular-nums" data-testid={`pricing-${id}-price`}>{price}</span>
          {per && <span className="nx-muted">{per}</span>}
        </p>
        <p className="min-h-[1.25rem] text-caption nx-muted">{note}</p>
      </div>
      <Features items={features} />
      <div className="mt-auto flex flex-col gap-2 pt-1">{action}</div>
    </section>
  );
  return pro
    ? <div className={`nx-pro-rim animate-nx-rim min-w-0 ${className}`}>{card}</div>
    : <div className={`min-w-0 ${className}`}>{card}</div>;
}

export default function PricingNextPage() {
  const { t, i18n } = useTranslation("next");
  const locale = localeOf(i18n.language);
  const { user, isAuthenticated, authRequired, signIn } = useAuthContext();
  const payments = usePayments();
  const checkout = useProCheckout("pricing");

  const signedIn = isAuthenticated || !authRequired;
  const plan = user?.tier === "admin" ? "admin" : user?.tier === "premium" ? "pro" : "free";
  const purchasesOff = payments?.subscriptions === false;
  const list = (key: string) => t(key, { returnObjects: true }) as string[];

  function proAction(iv: BillingInterval): ReactNode {
    if (plan === "pro") {
      return (
        <Link to="/settings/plan" className={BTN_SECONDARY}>
          <CreditCard aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("pricing.seeYourPlan")}
        </Link>
      );
    }
    if (plan === "admin") return <span className="text-caption nx-muted">{t("pricing.adminNote")}</span>;
    if (purchasesOff) return <span className={`${BTN_SECONDARY} pointer-events-none nx-muted`} aria-disabled="true">{t("settings.planSection.comingSoon")}</span>;
    if (!signedIn) {
      return <button type="button" onClick={signIn} className={BTN_PRIMARY} data-testid={`pricing-get-pro-${iv}`}>{t("pricing.signInForPro")}</button>;
    }
    return (
      <button type="button" onClick={() => checkout.start(iv)} disabled={checkout.busy} className={BTN_PRIMARY} data-testid={`pricing-get-pro-${iv}`}>
        {checkout.busy ? t("pricing.toStripe") : t(iv === "month" ? "pricing.getProMonthly" : "pricing.getProYearly")}
      </button>
    );
  }

  return (
    <AppFrame crumbs={[t("pricing.title")]}>
      <div className="mx-auto flex max-w-[1080px] flex-col gap-8 px-4 py-6 sm:px-8 sm:py-12" data-testid="pricing">
        <header className="mx-auto flex max-w-[60ch] flex-col items-center gap-2 text-center">
          <h1 className="text-[1.875rem] font-semibold tracking-[-0.02em] [text-wrap:balance]">{t("pricing.heading")}</h1>
          <p className="nx-muted [text-wrap:balance]">{t("pricing.lead")}</p>
        </header>

        <div className="grid items-stretch gap-4 md:grid-cols-3">
          <PlanCard
            id="free"
            className="order-last md:order-none"
            name={t("pricing.free")}
            tag={signedIn && plan === "free" ? <Pill tone="gray">{t("pricing.yourPlan")}</Pill> : undefined}
            price={dollars(0, locale)}
            note={t("pricing.freeNote")}
            features={list("pricing.freeFeatures")}
            action={signedIn ? null : (
              <>
                <button type="button" onClick={signIn} className={BTN_SECONDARY}>{t("pricing.signInFree")}</button>
                <span className="text-center text-caption nx-muted">{t("pricing.signedOutNote")}</span>
              </>
            )}
          />
          <PlanCard
            id="month"
            pro
            name={t("pricing.proMonthly")}
            tag={plan === "pro" ? <Pill tone="purple">{t("pricing.yourPlan")}</Pill> : undefined}
            price={dollars(PRICE_CENTS.month, locale)}
            per={t("pricing.aMonth")}
            note={t("pricing.monthNote")}
            features={list("pricing.proFeatures")}
            action={proAction("month")}
          />
          <PlanCard
            id="year"
            pro
            name={t("pricing.proYearly")}
            tag={<Pill tone="green">{t("pricing.save", { amount: dollars(yearlySavingsCents(), locale) })}</Pill>}
            price={dollars(PRICE_CENTS.year, locale)}
            per={t("pricing.aYear")}
            note={t("pricing.perMonthBilledYearly", { price: dollars(yearlyPerMonthCents(), locale) })}
            features={list("pricing.yearFeatures")}
            action={proAction("year")}
          />
        </div>
        {checkout.error && <p role="alert" className="rounded-xl bg-nx-pill-red-bg px-4 py-3 text-caption text-nx-pill-red">{t("pricing.checkoutFailed")}</p>}
        {purchasesOff && plan === "free" && <p className="text-center text-caption nx-muted">{t("pricing.comingSoonNote")}</p>}

        <section aria-labelledby="pricing-qa" className="flex w-full flex-col">
          <h2 id="pricing-qa" className="pb-3 text-body font-semibold">{t("pricing.qaTitle")}</h2>
          <dl className="flex flex-col">
            {(["cancel", "interval", "trial", "reports"] as const).map((k) => (
              <div key={k} className="grid gap-1 border-t border-nx-ink/10 py-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] sm:gap-6">
                <dt className="font-semibold">{t(`pricing.qa.${k}.q`)}</dt>
                <dd className="nx-muted">{t(`pricing.qa.${k}.a`, {
                  month: dollars(PRICE_CENTS.month, locale), year: dollars(PRICE_CENTS.year, locale),
                })}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
    </AppFrame>
  );
}
