// Settings → Sign-in methods (Phase 9, Item 121): the providers that reach this account, Add for the ones offered
// and not yet added, Remove while another remains. Accounts are never joined by email: adding one runs that
// provider's sign-in and attaches it here, or says it belongs to another account.
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Plus } from "lucide-react";
import {
  type SignInIdentity,
  type SignInProvider,
  type SignInProviderId,
  getSignInIdentities,
  removeSignInIdentity,
  startLinkProvider,
} from "../../lib/api";
import { PROVIDER_NAMES } from "../../lib/authNotice";
import { formatDate } from "../../lib/format";
import { ProviderMark } from "../auth/ProviderButtons";

export default function SignInMethods() {
  const { t } = useTranslation("common");
  const [rows, setRows] = useState<SignInIdentity[] | null>(null);
  const [available, setAvailable] = useState<SignInProvider[]>([]);
  const [busy, setBusy] = useState<SignInProviderId | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      getSignInIdentities().then(
        (data) => { setRows(data.identities); setAvailable(data.available); setError(null); },
        () => setError(t("auth.methods.error")),
      ),
    [t],
  );

  useEffect(() => {
    let alive = true;
    getSignInIdentities().then(
      (data) => { if (alive) { setRows(data.identities); setAvailable(data.available); } },
      () => { if (alive) setError(t("auth.methods.error")); },
    );
    return () => { alive = false; };
  }, [t]);

  async function add(provider: SignInProviderId) {
    setBusy(provider);
    try {
      window.location.assign(await startLinkProvider(provider, window.location.pathname));
    } catch {
      setError(t("auth.methods.error"));
      setBusy(null);
    }
  }

  async function remove(provider: SignInProviderId) {
    if (!window.confirm(t("auth.methods.removeConfirm", { provider: PROVIDER_NAMES[provider] }))) return;
    setBusy(provider);
    try {
      if ((await removeSignInIdentity(provider)) === "last") setError(t("auth.methods.lastOne"));
      await load();
    } catch {
      setError(t("auth.methods.error"));
    } finally {
      setBusy(null);
    }
  }

  if (rows === null) {
    return error ? <p className="text-body text-text-muted">{error}</p> : <p className="text-body text-text-muted">…</p>;
  }
  const have = new Set(rows.map((r) => r.provider));
  const addable = available.filter((p) => !have.has(p.id));
  const onlyOne = rows.length <= 1;

  return (
    <div className="flex flex-col gap-3" data-testid="signin-methods">
      <p className="text-caption text-text-muted">{t("auth.methods.body")}</p>
      <ul className="flex flex-col divide-y divide-dark-border">
        {rows.map((r) => (
          <li key={r.provider} className="flex items-center gap-3 py-3" data-provider={r.provider}>
            <ProviderMark provider={r.provider} />
            <div className="min-w-0 flex-1">
              <p className="text-body text-text-primary">{PROVIDER_NAMES[r.provider]}</p>
              <p className="truncate text-caption text-text-muted">
                {r.private_email ? t("auth.methods.hiddenEmail") : r.email ?? ""}
                {(r.private_email || r.email) && " · "}
                {t("auth.methods.added", { date: formatDate(new Date(r.added_at).toISOString()) })}
              </p>
            </div>
            {onlyOne ? (
              <span className="text-caption text-text-muted">{t("auth.methods.lastOneShort")}</span>
            ) : (
              <button
                type="button"
                onClick={() => remove(r.provider)}
                disabled={busy !== null}
                className="rounded-lg px-3 py-1.5 text-caption text-link hover:underline disabled:opacity-50"
              >
                {t("auth.methods.remove")}
              </button>
            )}
          </li>
        ))}
      </ul>
      {addable.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {addable.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => add(p.id)}
              disabled={busy !== null}
              className="inline-flex items-center gap-2 rounded-lg border border-dark-border px-3 py-2 text-caption text-text-primary hover:border-dark-border-strong disabled:opacity-50"
              data-add-provider={p.id}
            >
              <Plus aria-hidden className="h-4 w-4" />
              <ProviderMark provider={p.id} className="h-4 w-4" />
              {t("auth.methods.add", { provider: PROVIDER_NAMES[p.id] })}
              {p.test && <span className="opacity-70">({t("auth.testAccount")})</span>}
            </button>
          ))}
        </div>
      )}
      {error && <p className="text-caption text-state-warning" role="alert">{error}</p>}
    </div>
  );
}
