// Who may see a lot's Deep analysis (decision Item 124), as the server's entitlements say; the tab and the Overview's
// sixth tile share it. The server enforces it again on every read (`/api/deep-analysis` answers 403 otherwise); this
// only words the state.
import { useCallback, useEffect, useState } from "react";
import { getEntitlements, type DeepAnalysis, type Entitlements } from "../../lib/api";
import { useAuthContext } from "../../contexts/AuthContext";

/** This visit's analyses, by lot and language (the server keeps them too; this spares the round trip when a tab
    switch remounts the Deep analysis tab). */
export const analysisCache = new Map<string, DeepAnalysis>();

export type Gate = "checking" | "approximate" | "signed_out" | "unused" | "elsewhere" | "open" | "failed";

/** Two PINs name the same lot when their first ten digits match (the last four number a condo unit). */
export const sameLot = (a: string | null | undefined, b: string | null | undefined) => !!a && !!b && a.slice(0, 10) === b.slice(0, 10);

export function gateFor(e: Entitlements, pin: string): Gate {
  const d = e.deep_analysis;
  return d.unlimited || sameLot(d.free_pin, pin) ? "open" : d.free_left > 0 ? "unused" : "elsewhere";
}

export function useDeepGate(pin: string | null, exact: boolean) {
  const { isAuthenticated, authRequired } = useAuthContext();
  const signedIn = isAuthenticated || !authRequired;
  const key = `${pin}|${signedIn}`;
  // The server's answer for this lot and session, and a later change from this page (a claim), each keyed so a new
  // lot or a sign-in never shows the last one's state.
  const [answer, setAnswer] = useState<{ key: string; gate: Gate; ent: Entitlements | null } | null>(null);
  const [changed, setChanged] = useState<{ key: string; gate: Gate; ent: Entitlements | null } | null>(null);

  useEffect(() => {
    if (!exact || !pin || !signedIn) return;
    let alive = true;
    getEntitlements().then(
      (e) => { if (alive) setAnswer({ key, gate: gateFor(e, pin), ent: e }); },
      () => { if (alive) setAnswer({ key, gate: "failed", ent: null }); },
    );
    return () => { alive = false; };
  }, [key, exact, pin, signedIn]);

  const current = changed?.key === key ? changed : answer?.key === key ? answer : null;
  const gate: Gate = !exact || !pin ? "approximate" : !signedIn ? "signed_out" : current?.gate ?? "checking";
  const ent = current?.ent ?? null;
  const change = useCallback((gate: Gate, ent: Entitlements | null) => setChanged({ key, gate, ent }), [key]);
  return { gate, ent, change };
}
