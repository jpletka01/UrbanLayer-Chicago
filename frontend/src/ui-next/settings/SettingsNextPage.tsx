// Settings in the new UI (owner-approved design B, 2026-11-13; canvas "Settings Wireframe"): the sections on the left,
// one shown at a time at its own address (/settings/<section>). On a phone, /settings is the list of sections and
// each opens on its own with a way back. Built from the new UI's own pieces: the frame, Block, StatTile, Pill,
// the provider buttons. Signed out, only Preferences and a quiet sign-in line: nothing is locked.
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import {
  Bookmark, Check, ChevronLeft, ChevronRight, CircleUser, FileText, Gauge, KeyRound, LogIn, LogOut, MessageCircle,
  Monitor, Moon, Search, SlidersHorizontal, Sun, Ticket, Trash2, type LucideIcon,
} from "lucide-react";
import { useAuthContext } from "../../contexts/AuthContext";
import { useThemeContext } from "../../contexts/ThemeContext";
import {
  createBillingPortal, deleteAccount, fetchMyPurchases, getSubscription, getUsage, listConversations, redeemVoucher,
  savedApi, type ReportPurchase, type Usage,
} from "../../lib/api";
import { PROVIDER_NAMES } from "../../lib/authNotice";
import { formatDate } from "../../lib/format";
import { useSignInMethods } from "../../lib/useSignInMethods";
import ProviderButtons, { ProviderMark } from "../../components/auth/ProviderButtons";
import { PurchaseRow } from "../../components/settings/PurchaseRow";
import { AppFrame } from "../frame/AppFrame";
import { NEXT_PROVIDER_BUTTON } from "../frame/signInLook";
import { STROKE } from "../icons";
import { Block, Pill, StatTile } from "../ui/Blocks";
import { sectionFrom, sectionsFor, usedShare, type SectionId } from "./settingsModel";

const ICONS: Record<SectionId, LucideIcon> = {
  account: CircleUser,
  plan: Gauge,
  signin: KeyRound,
  preferences: SlidersHorizontal,
  things: Bookmark,
  reports: FileText,
  delete: Trash2,
};

const BTN_PRIMARY = "inline-flex items-center justify-center gap-2 rounded-full bg-nx-primary px-4 py-2 font-semibold text-nx-primary-fg disabled:opacity-50 touch-target";
const BTN_SECONDARY = "inline-flex items-center justify-center gap-2 rounded-full px-3.5 py-2 font-medium ring-1 ring-inset ring-nx-ink/20 hover:bg-nx-ink/5 disabled:opacity-50 touch-target";
const FIELD = "min-w-0 rounded-xl bg-nx-page px-3 py-2 ring-1 ring-inset ring-nx-ink/15 placeholder:text-nx-ink/50 focus:outline-none focus:ring-2 focus:ring-nx-ink/40 touch-field";

export default function SettingsNextPage() {
  const { t } = useTranslation("next");
  const { user, isAuthenticated, authRequired, signIn } = useAuthContext();
  const params = useParams<{ section?: string }>();
  const [purchases, setPurchases] = useState<ReportPurchase[]>([]);
  const signedIn = isAuthenticated || !authRequired;

  useEffect(() => {
    if (!signedIn) return;
    let alive = true;
    fetchMyPurchases().then((p) => { if (alive) setPurchases(p); }, () => {});
    return () => { alive = false; };
  }, [signedIn]);

  const sections = sectionsFor({ signedIn, authRequired, hasReports: purchases.length > 0 });
  const current = sectionFrom(params.section, sections);
  const onList = !params.section; // a phone shows the list at /settings
  const label = (s: SectionId) => t(`settings.sections.${s}`);

  return (
    <AppFrame crumbs={onList ? [t("settings.title")] : [<Link key="s" to="/settings" className="nx-muted hover:text-nx-ink">{t("settings.title")}</Link>, label(current)]}>
      <div className="mx-auto flex max-w-[1040px] flex-col gap-6 px-4 py-6 sm:px-8 sm:py-10" data-testid="settings">
        <h1 className={`text-[1.875rem] font-semibold tracking-[-0.02em] ${onList ? "" : "hidden md:block"}`}>{t("settings.title")}</h1>

        {!signedIn && (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption nx-muted" data-testid="settings-signin">
            {t("settings.signedOut")}
            <button type="button" onClick={signIn} className="inline-flex items-center gap-1.5 font-semibold text-nx-ink underline underline-offset-2 touch-target">
              <LogIn aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("frame.signIn")}
            </button>
          </p>
        )}

        <div className="flex flex-wrap items-start gap-8">
          {/* Desktop: the section list beside the section. */}
          <nav aria-label={t("settings.sectionsLabel")} className="hidden w-[220px] shrink-0 flex-col gap-0.5 md:flex" data-testid="settings-nav">
            {sections.map((s) => <SectionLink key={s} id={s} current={s === current} label={label(s)} />)}
            {signedIn && authRequired && <><div className="my-2 border-t border-nx-ink/10" /><SignOutButton className="h-9 rounded-xl px-2.5 hover:bg-nx-ink/5" /></>}
          </nav>

          {/* Phone, at /settings: the account card and the sections as rows. */}
          {onList && (
            <div className="flex w-full flex-col gap-4 md:hidden" data-testid="settings-phone-list">
              {signedIn && user && <AccountCard compact />}
              <nav aria-label={t("settings.sectionsLabel")} className="overflow-hidden rounded-2xl bg-nx-block">
                {sections.filter((s) => s !== "delete").map((s, i) => (
                  <Link key={s} to={`/settings/${s}`} className={`flex min-h-[52px] items-center gap-3 px-4 ${i ? "border-t border-nx-ink/10" : ""}`}>
                    {(() => { const I = ICONS[s]; return <I aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />; })()}
                    <span className="flex-1">{label(s)}</span>
                    <ChevronRight aria-hidden className="h-4 w-4 nx-muted" strokeWidth={STROKE} />
                  </Link>
                ))}
              </nav>
              {signedIn && authRequired && (
                <div className="overflow-hidden rounded-2xl bg-nx-block">
                  <SignOutButton className="min-h-[52px] w-full px-4" />
                  <Link to="/settings/delete" className="flex min-h-[52px] items-center gap-3 border-t border-nx-ink/10 px-4 text-nx-pill-red">
                    <Trash2 aria-hidden className="h-4 w-4" strokeWidth={STROKE} /><span className="flex-1">{label("delete")}</span>
                    <ChevronRight aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
                  </Link>
                </div>
              )}
            </div>
          )}

          <div className={`min-w-0 flex-[999_1_420px] flex-col gap-4 ${onList ? "hidden md:flex" : "flex"}`} data-testid={`settings-${current}`}>
            <Link to="/settings" className="inline-flex items-center gap-1 self-start text-caption font-medium nx-muted md:hidden touch-target">
              <ChevronLeft aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("settings.title")}
            </Link>
            <h2 className="text-[1.5rem] font-semibold tracking-[-0.02em] md:sr-only">{label(current)}</h2>
            {current === "account" && <AccountSection />}
            {current === "plan" && <PlanSection />}
            {current === "signin" && <SignInSection />}
            {current === "preferences" && <PreferencesSection />}
            {current === "things" && <ThingsSection />}
            {current === "reports" && <ReportsSection purchases={purchases} onChanged={() => fetchMyPurchases().then(setPurchases, () => {})} />}
            {current === "delete" && <DeleteSection />}
          </div>
        </div>
      </div>
    </AppFrame>
  );
}

function SectionLink({ id, current, label }: { id: SectionId; current: boolean; label: string }) {
  const Icon = ICONS[id];
  return (
    <Link
      to={`/settings/${id}`}
      aria-current={current ? "page" : undefined}
      className={`flex h-9 items-center gap-2.5 rounded-xl px-2.5 ${current ? "bg-nx-ink/5 font-semibold" : "hover:bg-nx-ink/5"} ${id === "delete" ? "text-nx-pill-red" : ""}`}
    >
      <Icon aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />{label}
    </Link>
  );
}

function SignOutButton({ className }: { className: string }) {
  const { t } = useTranslation("next");
  const { signOut } = useAuthContext();
  const navigate = useNavigate();
  return (
    <button type="button" onClick={async () => { await signOut(); navigate("/"); }} className={`flex items-center gap-2.5 text-left ${className}`} data-testid="settings-signout">
      <LogOut aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />{t("frame.signOut")}
    </button>
  );
}

function planOf(tier: string | undefined): "free" | "pro" | "admin" {
  return tier === "admin" ? "admin" : tier === "premium" ? "pro" : "free";
}

function AccountCard({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation("next");
  const { user } = useAuthContext();
  if (!user) return null;
  const plan = planOf(user.tier);
  const initial = (user.name || user.email || "?").trim()[0]?.toUpperCase() ?? "?";
  return (
    <div className={`flex items-center gap-3 rounded-2xl bg-nx-block ${compact ? "p-4" : "p-5 sm:p-6"}`} data-testid="settings-account-card">
      {user.picture_url ? (
        <img src={user.picture_url} alt="" referrerPolicy="no-referrer" className={`${compact ? "h-11 w-11" : "h-14 w-14"} shrink-0 rounded-full`} />
      ) : (
        <span aria-hidden className={`${compact ? "h-11 w-11" : "h-14 w-14"} grid shrink-0 place-items-center rounded-full bg-nx-stat-a font-semibold text-nx-card-ink`}>{initial}</span>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{user.name || t("frame.account")}</span>
          <Pill tone={plan === "free" ? "gray" : "purple"}>{t(`settings.plan.${plan}`)}</Pill>
        </span>
        {user.email && <span className="truncate text-caption nx-muted">{user.email}</span>}
      </div>
    </div>
  );
}

function AccountSection() {
  const { t } = useTranslation("next");
  return (
    <>
      <AccountCard />
      <p className="text-caption nx-muted">{t("settings.account.fromSignIn")}</p>
    </>
  );
}

function PlanSection() {
  const { t, i18n } = useTranslation("next");
  const { user, checkAuth } = useAuthContext();
  const [usage, setUsage] = useState<Usage | null>(null);
  const [sub, setSub] = useState<Awaited<ReturnType<typeof getSubscription>> | null>(null);
  const [portalBusy, setPortalBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    getUsage().then((u) => { if (alive) setUsage(u); });
    getSubscription().then((s) => { if (alive) setSub(s); }, () => {});
    return () => { alive = false; };
  }, []);

  const plan = planOf(user?.tier);
  const share = usage ? usedShare(usage.used, usage.limit) : null;
  const back = usage?.resets_on
    ? new Intl.DateTimeFormat(i18n.language.startsWith("es") ? "es-MX" : "en-US", { month: "short", day: "numeric" })
      .format(new Date(`${usage.resets_on}T12:00:00`))
    : null;
  const proLimit = usage?.pro_limit ?? 200;

  async function manageBilling() {
    setPortalBusy(true);
    try {
      window.location.assign((await createBillingPortal()).url);
    } catch {
      setPortalBusy(false);
    }
  }

  return (
    <>
      {usage && usage.limit != null && (
        <ul className="grid grid-cols-2 gap-3 sm:gap-4" data-testid="settings-usage">
          <StatTile
            tone="a"
            label={t("settings.planSection.used")}
            figure={usage.used}
            unit={t("settings.planSection.ofLimit", { limit: usage.limit })}
            note={
              <span role="img" aria-label={t("settings.planSection.usedAria", { used: usage.used, limit: usage.limit })} className="mt-1 block h-2 overflow-hidden rounded bg-nx-card-ink/10">
                <span className="block h-full rounded bg-nx-card-ink" style={{ width: `${(share ?? 0) * 100}%` }} />
              </span>
            }
          />
          <StatTile tone="b" label={t("settings.planSection.back")} figure={back ?? "—"} note={t("settings.planSection.everyMonth")} />
        </ul>
      )}

      <Block title={t("settings.planSection.yourPlan")} icon={Gauge} labelledBy="settings-plan" aside={<Pill tone={plan === "free" ? "gray" : "purple"}>{t(`settings.plan.${plan}`)}</Pill>}>
        {plan === "free" && (
          <>
            <p>{t("settings.planSection.freeBody", { limit: usage?.limit ?? 50 })}</p>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-nx-ink/10 pt-4">
              <span className="nx-muted">{t("settings.planSection.proLine", { limit: proLimit })}</span>
              <Pill tone="gray">{t("settings.planSection.comingSoon")}</Pill>
            </div>
          </>
        )}
        {plan === "pro" && (
          <>
            <p>
              {sub?.comp_until
                ? t("settings.planSection.compBody", { limit: proLimit, date: formatDate(new Date(sub.comp_until).toISOString()) })
                : t("settings.planSection.proBody", { limit: proLimit })}
            </p>
            {sub?.subscription_active && (
              <button type="button" onClick={manageBilling} disabled={portalBusy} className={`${BTN_SECONDARY} self-start`}>
                {t("settings.planSection.manageBilling")}
              </button>
            )}
          </>
        )}
        {plan === "admin" && <p>{t("settings.planSection.adminBody")}</p>}
      </Block>

      <AccessCode onRedeemed={() => { checkAuth(); getSubscription().then(setSub, () => {}); }} />
    </>
  );
}

function AccessCode({ onRedeemed }: { onRedeemed: () => void }) {
  const { t } = useTranslation("next");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  async function apply() {
    const trimmed = code.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setMessage(null);
    const result = await redeemVoucher(trimmed);
    setBusy(false);
    if (result.ok) {
      setCode("");
      setMessage({ ok: true, text: t("settings.code.success", { date: formatDate(new Date(result.premium_until).toISOString()) }) });
      onRedeemed();
    } else {
      setMessage({ ok: false, text: t(`settings.code.${result.reason}`) });
    }
  }

  return (
    <Block title={t("settings.code.title")} icon={Ticket} labelledBy="settings-code">
      <form className="flex flex-wrap items-center gap-3" onSubmit={(e) => { e.preventDefault(); apply(); }}>
        <label htmlFor="settings-code-input" className="nx-muted w-full sm:w-auto sm:flex-1">{t("settings.code.body")}</label>
        <input id="settings-code-input" value={code} onChange={(e) => setCode(e.target.value)} placeholder="UL-XXXXXXXX"
          autoComplete="off" spellCheck={false} className={`${FIELD} flex-1 uppercase placeholder:normal-case sm:w-56 sm:flex-none`} />
        <button type="submit" disabled={busy || !code.trim()} className={BTN_PRIMARY}>{busy ? t("settings.code.applying") : t("settings.code.apply")}</button>
      </form>
      {message && (
        <p role={message.ok ? "status" : "alert"} className={`flex items-center gap-2 rounded-xl px-4 py-3 text-caption ${message.ok ? "bg-nx-pill-green-bg text-nx-pill-green" : "bg-nx-pill-red-bg text-nx-pill-red"}`}>
          {message.ok && <Check aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />}{message.text}
        </p>
      )}
    </Block>
  );
}

function SignInSection() {
  const { t } = useTranslation("next");
  const { t: tc } = useTranslation("common");
  const m = useSignInMethods();
  const errorText = m.error === "last" ? tc("auth.methods.lastOne") : m.error ? tc("auth.methods.error") : null;
  const onlyOne = (m.rows?.length ?? 0) <= 1;
  return (
    <>
      <Block title={t("settings.signin.ways")} icon={KeyRound} labelledBy="settings-ways">
        <p className="nx-muted">{t("settings.signin.body")}</p>
        {m.rows === null ? (
          <p role="status" className="nx-muted">{errorText ?? t("frame.loading")}</p>
        ) : (
          <ul className="flex flex-col" data-testid="signin-methods">
            {m.rows.map((r) => (
              <li key={r.provider} className="flex flex-wrap items-center gap-3 border-t border-nx-ink/10 py-3.5" data-provider={r.provider}>
                <ProviderMark provider={r.provider} />
                <span className="flex min-w-0 flex-[1_1_200px] flex-col">
                  <span className="font-semibold">{PROVIDER_NAMES[r.provider]}</span>
                  <span className="truncate text-caption nx-muted">
                    {[r.private_email ? tc("auth.methods.hiddenEmail") : r.email, tc("auth.methods.added", { date: formatDate(new Date(r.added_at).toISOString()) })]
                      .filter(Boolean).join(" · ")}
                  </span>
                </span>
                {onlyOne ? (
                  <span className="text-caption nx-muted">{tc("auth.methods.lastOneShort")}</span>
                ) : (
                  <button type="button" disabled={m.busy !== null} className={BTN_SECONDARY}
                    onClick={() => m.remove(r.provider, () => window.confirm(tc("auth.methods.removeConfirm", { provider: PROVIDER_NAMES[r.provider] })))}>
                    {tc("auth.methods.remove")}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        {errorText && m.rows !== null && <p role="alert" className="rounded-xl bg-nx-pill-red-bg px-4 py-3 text-caption text-nx-pill-red">{errorText}</p>}
      </Block>
      {m.addable.length > 0 && (
        <Block title={t("settings.signin.add")} labelledBy="settings-add">
          <div className="max-w-sm">
            <ProviderButtons providers={m.addable} onChoose={(p) => m.add(p)} buttonClassName={NEXT_PROVIDER_BUTTON} />
          </div>
          <p className="text-caption nx-muted">{t("settings.signin.addNote")}</p>
        </Block>
      )}
    </>
  );
}

function PreferencesSection() {
  const { t, i18n } = useTranslation("next");
  const { theme, setTheme } = useThemeContext();
  const lang = i18n.language.startsWith("es") ? "es" : "en";
  const themes: { id: "light" | "dark" | "system"; icon: LucideIcon }[] = [
    { id: "light", icon: Sun }, { id: "dark", icon: Moon }, { id: "system", icon: Monitor },
  ];
  return (
    <Block title={t("settings.sections.preferences")} icon={SlidersHorizontal} labelledBy="settings-prefs">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span id="settings-theme-label">{t("frame.theme")}</span>
        <div role="radiogroup" aria-labelledby="settings-theme-label" className="inline-flex rounded-full p-1 ring-1 ring-inset ring-nx-ink/15">
          {themes.map(({ id, icon: Icon }) => (
            <button key={id} type="button" role="radio" aria-checked={theme === id} onClick={() => setTheme(id)}
              className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 touch-target ${theme === id ? "bg-nx-primary font-semibold text-nx-primary-fg" : "hover:bg-nx-ink/5"}`}>
              <Icon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t(`frame.themes.${id}`)}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-nx-ink/10 pt-4">
        <label htmlFor="settings-language">{t("frame.language")}</label>
        <select id="settings-language" value={lang} onChange={(e) => i18n.changeLanguage(e.target.value)} className={`${FIELD} appearance-none pr-8`}>
          <option value="en">English</option>
          <option value="es">Español</option>
        </select>
      </div>
    </Block>
  );
}

function ThingsSection() {
  const { t } = useTranslation("next");
  const [counts, setCounts] = useState<{ lots?: number; searches?: number; chats?: number }>({});
  useEffect(() => {
    let alive = true;
    savedApi.lots().then((r) => { if (alive) setCounts((c) => ({ ...c, lots: r.lots.length })); }, () => {});
    savedApi.searches().then((r) => { if (alive) setCounts((c) => ({ ...c, searches: r.searches.length })); }, () => {});
    listConversations().then((r) => { if (alive) setCounts((c) => ({ ...c, chats: r.length })); }, () => {});
    return () => { alive = false; };
  }, []);
  const rows: { to: string; label: string; icon: LucideIcon; n?: number }[] = [
    { to: "/saved", label: t("settings.things.lots"), icon: Bookmark, n: counts.lots },
    { to: "/saved?tab=searches", label: t("settings.things.searches"), icon: Search, n: counts.searches },
    { to: "/chat", label: t("settings.things.chats"), icon: MessageCircle, n: counts.chats },
  ];
  return (
    <Block title={t("settings.sections.things")} icon={Bookmark} labelledBy="settings-things">
      <ul className="flex flex-col">
        {rows.map(({ to, label, icon: Icon, n }) => (
          <li key={to} className="border-t border-nx-ink/10 first:border-t-0">
            <Link to={to} className="flex min-h-[44px] items-center gap-3 py-2 hover:underline">
              <Icon aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />
              <span className="flex-1">{label}</span>
              {n != null && <span className="text-caption nx-muted tabular-nums">{n}</span>}
              <ChevronRight aria-hidden className="h-4 w-4 nx-muted" strokeWidth={STROKE} />
            </Link>
          </li>
        ))}
      </ul>
    </Block>
  );
}

function ReportsSection({ purchases, onChanged }: { purchases: ReportPurchase[]; onChanged: () => void }) {
  const { t } = useTranslation("next");
  return (
    <Block title={t("settings.sections.reports")} icon={FileText} labelledBy="settings-reports">
      <p className="text-caption nx-muted">{t("settings.reports.body")}</p>
      <div className="flex flex-col">
        {purchases.map((p) => <PurchaseRow key={p.id} purchase={p} onDownloaded={onChanged} />)}
      </div>
    </Block>
  );
}

function DeleteSection() {
  const { t } = useTranslation("next");
  const [open, setOpen] = useState(false);
  return (
    <Block title={t("settings.sections.delete")} icon={Trash2} labelledBy="settings-delete">
      <p>{t("settings.delete.body")}</p>
      <button type="button" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 self-start rounded-full bg-nx-pill-red-bg px-4 py-2 font-semibold text-nx-pill-red touch-target" data-testid="settings-delete-open">
        <Trash2 aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("settings.delete.open")}
      </button>
      {open && <DeleteDialog onClose={() => setOpen(false)} />}
    </Block>
  );
}

function DeleteDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("next");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const word = t("settings.delete.word");
  const armed = text.trim().toLowerCase() === word.toLowerCase();

  async function confirm() {
    setBusy(true);
    setError(false);
    try {
      await deleteAccount();
      window.location.assign("/"); // cookies are cleared by the server; a full load resets everything
    } catch {
      setBusy(false);
      setError(true);
    }
  }

  return (
    <Dialog.Root open onOpenChange={(o) => { if (!o) onClose(); }}>
      <Dialog.Portal>
        <div className="ui-next">
          <Dialog.Overlay className="fixed inset-0 z-[65] bg-black/30" />
          <Dialog.Content data-testid="settings-delete-dialog"
            className="fixed inset-x-0 bottom-0 z-[70] flex flex-col gap-3 rounded-t-3xl bg-nx-page p-5 text-nx-ink shadow-[0_-8px_32px_rgb(0_0_0/0.16)] sm:inset-x-auto sm:bottom-auto sm:left-1/2 sm:top-1/2 sm:w-[min(28rem,calc(100vw-2rem))] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-3xl">
            <Dialog.Title className="text-[1.0625rem] font-semibold">{t("settings.delete.title")}</Dialog.Title>
            <Dialog.Description className="nx-muted">{t("settings.delete.dialogBody")}</Dialog.Description>
            <label htmlFor="settings-delete-word" className="text-caption">{t("settings.delete.typeWord", { word })}</label>
            <input id="settings-delete-word" value={text} onChange={(e) => setText(e.target.value)} autoComplete="off" className={FIELD} autoFocus />
            {error && <p role="alert" className="rounded-xl bg-nx-pill-red-bg px-4 py-3 text-caption text-nx-pill-red">{t("settings.delete.failed")}</p>}
            <div className="flex flex-wrap justify-end gap-2">
              <Dialog.Close asChild><button type="button" className={BTN_SECONDARY}>{t("settings.delete.cancel")}</button></Dialog.Close>
              <button type="button" onClick={confirm} disabled={!armed || busy} className="inline-flex items-center gap-2 rounded-full bg-nx-pill-red px-4 py-2 font-semibold text-nx-page disabled:opacity-40 touch-target" data-testid="settings-delete-confirm">
                {busy ? t("settings.delete.deleting") : t("settings.delete.confirm")}
              </button>
            </div>
          </Dialog.Content>
        </div>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

