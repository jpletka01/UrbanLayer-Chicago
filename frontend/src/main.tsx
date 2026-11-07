import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import * as Sentry from '@sentry/react'
import 'mapbox-gl/dist/mapbox-gl.css'
import './lib/i18n'
import './index.css'
// The new UI's tokens: every rule is scoped to .ui-next, so this changes nothing on today's pages.
import './ui-next/ui-next.css'
import { initTracking, track } from './lib/tracking'

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 0.1,
  });
}

initTracking();

// Microsoft Clarity session replay — validation-window instrumentation,
// disclosed on /privacy. Inert unless a project ID is provided at build time.
// Official bootstrap snippet: define the window.clarity queue-stub function
// BEFORE the remote tag loads. Clarity's own duplicate-load guard inside
// clarity.js calls window.clarity("event", …); injecting the bare <script> tag
// skipped the stub, so that call threw "a[c] is not a function" (Sentry, 2026-07-06).
if (import.meta.env.VITE_CLARITY_ID) {
  type ClarityFn = { (...args: unknown[]): void; q?: unknown[] };
  const w = window as unknown as { clarity?: ClarityFn };
  w.clarity = w.clarity || function (...args: unknown[]) {
    (w.clarity!.q = w.clarity!.q || []).push(args);
  };
  const s = document.createElement("script");
  s.async = true;
  s.src = `https://www.clarity.ms/tag/${import.meta.env.VITE_CLARITY_ID}`;
  const first = document.getElementsByTagName("script")[0];
  first.parentNode?.insertBefore(s, first);
}

import { App } from './App.tsx'
import { AboutPage } from './components/AboutPage.tsx'
import { AdminDashboard } from './components/AdminDashboard.tsx'
import PricingPage from './components/PricingPage.tsx'
import SettingsPage from './components/SettingsPage.tsx'
import ScorecardPage from './components/ScorecardPage.tsx'
import { PrivacyPage } from './components/PrivacyPage.tsx'
import { NotFoundPage } from './components/NotFoundPage.tsx'
import DiscoveryPage from './discovery/DiscoveryPage.tsx'
import { AuthProvider } from './contexts/AuthContext.tsx'
import { ThemeProvider } from './contexts/ThemeContext.tsx'
import { SelectedParcelProvider } from './contexts/SelectedParcelContext.tsx'
import ProtectedRoute from './components/ProtectedRoute.tsx'
import { SegmentPrompt } from './components/SegmentPrompt.tsx'
import { UiVersionProvider } from './ui-next/UiVersionProvider.tsx'
import { useUiVersion } from './ui-next/uiVersionContext.ts'
import { VersionedRoute } from './ui-next/VersionedRoute.tsx'
import { PreviewBadge } from './ui-next/PreviewBadge.tsx'
import { entryForPath, isReady } from './ui-next/readiness.ts'

function TrackPageView() {
  const { pathname } = useLocation();
  const { version } = useUiVersion();
  useEffect(() => {
    // In the preview, page_view names the page from the readiness registry (tracking adds ui_version).
    const entry = version === "next" ? entryForPath(pathname) : undefined;
    track("page_view", entry && isReady(entry.id) ? { page_name: entry.analytics } : undefined);
  }, [pathname, version]);
  return null;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <UiVersionProvider>
      <ThemeProvider>
        <AuthProvider>
          <SelectedParcelProvider>
          <TrackPageView />
          {/* Post-sign-in "what best describes you" — renders nothing unless
              a sign-in just completed and no segment is stored. */}
          <SegmentPrompt />
          <PreviewBadge />
          <Routes>
            <Route path="/" element={<App />} />
            <Route path="/c/:id" element={<App />} />
            <Route path="/s/:shareToken" element={<App />} />
            {/* Versioned routes: today's page unless ?ui=next is on and the readiness registry says ready. */}
            <Route path="/scorecard" element={<VersionedRoute id="profile" old={<ScorecardPage />} />} />
            {/* /explore retired 2026-06-14 — Discovery is a strict superset. Redirect legacy links. */}
            <Route path="/explore" element={<Navigate to="/discovery" replace />} />
            <Route path="/discovery" element={<VersionedRoute id="discovery" old={<DiscoveryPage />} />} />
            <Route path="/pricing" element={<PricingPage />} />
            <Route path="/settings" element={
              <ProtectedRoute>
                <SettingsPage />
              </ProtectedRoute>
            } />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/admin" element={
              <ProtectedRoute tier="admin">
                <AdminDashboard />
              </ProtectedRoute>
            } />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
          </SelectedParcelProvider>
        </AuthProvider>
      </ThemeProvider>
      </UiVersionProvider>
    </BrowserRouter>
  </StrictMode>,
)
