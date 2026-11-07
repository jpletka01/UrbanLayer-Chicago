// UiVersionProvider (decision Items 75–76): holds the visitor's UI version for the whole app.
// Reads `?ui=` on the first render and on every later navigation (a shared preview link, Back/Forward),
// remembers it (uiVersion.ts), removes the parameter from the address bar with a replace, and tags
// analytics and Sentry with the version. With the build-time switch off it always says "old".
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import * as Sentry from "@sentry/react";
import { setUiVersion } from "../lib/tracking";
import {
  previewEnabled,
  readStoredVersion,
  resolveUiVersion,
  versionFromParam,
  withoutUiParam,
  writeStoredVersion,
  type UiVersion,
} from "./uiVersion";

import { UiVersionContext } from "./uiVersionContext";

export function UiVersionProvider({
  children,
  enabled = previewEnabled(),
}: {
  children: ReactNode;
  /** Tests pass this; the app reads the env. */
  enabled?: boolean;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [version, setVersionState] = useState<UiVersion>(() =>
    resolveUiVersion({ search: location.search, stored: readStoredVersion(), enabled }),
  );

  const setVersion = useCallback((v: UiVersion) => {
    const next = enabled ? v : "old";
    writeStoredVersion(next);
    setVersionState(next);
  }, [enabled]);

  // A `?ui=` on any navigation (first load, a pasted link, Back/Forward to an entry that still has it):
  // apply it, remember it, and take it out of the address bar without adding a history entry.
  const asked = versionFromParam(location.search);
  useEffect(() => {
    if (asked === null) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing with the URL, once per navigation
    setVersion(asked);
    navigate(
      { pathname: location.pathname, search: withoutUiParam(location.search), hash: location.hash },
      { replace: true, state: location.state },
    );
  }, [asked, location.pathname, location.search, location.hash, location.state, navigate, setVersion]);

  useEffect(() => {
    setUiVersion(version);
    Sentry.setTag("ui_version", version);
  }, [version]);

  const value = useMemo(() => ({ version, enabled, setVersion }), [version, enabled, setVersion]);
  return <UiVersionContext.Provider value={value}>{children}</UiVersionContext.Provider>;
}
