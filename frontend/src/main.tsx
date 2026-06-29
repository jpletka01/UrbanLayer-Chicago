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

import { App } from './App.tsx'
import { AboutPage } from './components/AboutPage.tsx'
import { AdminDashboard } from './components/AdminDashboard.tsx'
import PricingPage from './components/PricingPage.tsx'
import ScorecardPage from './components/ScorecardPage.tsx'
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
            <Route path="/about" element={<AboutPage />} />
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
