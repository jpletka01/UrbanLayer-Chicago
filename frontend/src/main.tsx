import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import * as Sentry from '@sentry/react'
import 'mapbox-gl/dist/mapbox-gl.css'
import './lib/i18n'
import './index.css'
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
import DiscoveryPage from './discovery/DiscoveryPage.tsx'
import { AuthProvider } from './contexts/AuthContext.tsx'
import { ThemeProvider } from './contexts/ThemeContext.tsx'
import { SelectedParcelProvider } from './contexts/SelectedParcelContext.tsx'
import ProtectedRoute from './components/ProtectedRoute.tsx'

function TrackPageView() {
  const { pathname } = useLocation();
  useEffect(() => { track("page_view"); }, [pathname]);
  return null;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <SelectedParcelProvider>
          <TrackPageView />
          <Routes>
            <Route path="/" element={<App />} />
            <Route path="/c/:id" element={<App />} />
            <Route path="/s/:shareToken" element={<App />} />
            <Route path="/scorecard" element={<ScorecardPage />} />
            {/* /explore retired 2026-06-14 — Discovery is a strict superset. Redirect legacy links. */}
            <Route path="/explore" element={<Navigate to="/discovery" replace />} />
            <Route path="/discovery" element={<DiscoveryPage />} />
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
          </Routes>
          </SelectedParcelProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
)
