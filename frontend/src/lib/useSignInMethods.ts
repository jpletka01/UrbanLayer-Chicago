// The account's sign-in methods (Phase 9, Item 121), shared by today's Settings and the new UI's: the list, the
// methods that can still be added, Add (through the link endpoint, coming back to this page) and Remove (refused
// on the last one by the server; the words come from the caller's namespace).
import { useCallback, useEffect, useState } from "react";
import {
  type SignInIdentity,
  type SignInProvider,
  type SignInProviderId,
  getSignInIdentities,
  removeSignInIdentity,
  startLinkProvider,
} from "./api";

export type SignInMethodsError = "load" | "action" | "last";

export interface SignInMethods {
  rows: SignInIdentity[] | null;
  /** Offered by this server and not on the account yet. */
  addable: SignInProvider[];
  busy: SignInProviderId | null;
  error: SignInMethodsError | null;
  add: (provider: SignInProviderId) => Promise<void>;
  /** Removes after `confirm` says yes. */
  remove: (provider: SignInProviderId, confirm: () => boolean) => Promise<void>;
}

export function useSignInMethods(): SignInMethods {
  const [rows, setRows] = useState<SignInIdentity[] | null>(null);
  const [available, setAvailable] = useState<SignInProvider[]>([]);
  const [busy, setBusy] = useState<SignInProviderId | null>(null);
  const [error, setError] = useState<SignInMethodsError | null>(null);

  const load = useCallback(
    () =>
      getSignInIdentities().then(
        (data) => { setRows(data.identities); setAvailable(data.available); },
        () => setError("load"),
      ),
    [],
  );

  useEffect(() => {
    let alive = true;
    getSignInIdentities().then(
      (data) => { if (alive) { setRows(data.identities); setAvailable(data.available); } },
      () => { if (alive) setError("load"); },
    );
    return () => { alive = false; };
  }, []);

  const add = useCallback(async (provider: SignInProviderId) => {
    setBusy(provider);
    setError(null);
    try {
      window.location.assign(await startLinkProvider(provider, window.location.pathname));
    } catch {
      setError("action");
      setBusy(null);
    }
  }, []);

  const remove = useCallback(async (provider: SignInProviderId, confirm: () => boolean) => {
    if (!confirm()) return;
    setBusy(provider);
    setError(null);
    try {
      if ((await removeSignInIdentity(provider)) === "last") setError("last");
      await load();
    } catch {
      setError("action");
    } finally {
      setBusy(null);
    }
  }, [load]);

  const have = new Set((rows ?? []).map((r) => r.provider));
  return { rows, addable: available.filter((p) => !have.has(p.id)), busy, error, add, remove };
}
