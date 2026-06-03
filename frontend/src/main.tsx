import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import * as Sentry from '@sentry/react'
import 'mapbox-gl/dist/mapbox-gl.css'
import './index.css'

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 0.1,
  });
}
import { App } from './App.tsx'
import { AboutPage } from './components/AboutPage.tsx'
import { AdminDashboard } from './components/AdminDashboard.tsx'
import { AuthProvider } from './contexts/AuthContext.tsx'
import ProtectedRoute from './components/ProtectedRoute.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/c/:id" element={<App />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/admin" element={
            <ProtectedRoute tier="admin">
              <AdminDashboard />
            </ProtectedRoute>
          } />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
