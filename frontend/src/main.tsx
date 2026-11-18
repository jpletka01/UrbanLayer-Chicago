import { StrictMode, Suspense, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import * as Sentry from '@sentry/react'
import './lib/i18n'
import './index.css'
import './app/app.css'
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

import { AuthProvider } from './contexts/AuthContext.tsx'
import { ThemeProvider } from './contexts/ThemeContext.tsx'
import { SelectedParcelProvider } from './contexts/SelectedParcelContext.tsx'
import AuthOverlays from './app/frame/AuthOverlays.tsx'
import { SegmentQuestion } from './app/frame/SegmentQuestion.tsx'
import { FrameOutline } from './app/frame/FrameOutline.tsx'
import { PAGES } from './app/pages.ts'
import { pageNameFor } from './app/destinations.ts'
import { isChatDoor } from './app/chatDoor.ts'


function TrackPageView() {
  const { pathname } = useLocation();
  useEffect(() => {
    track("page_view", { page_name: pageNameFor(pathname) });
  }, [pathname]);
  return null;
}

/** One page, loaded on demand. /chat, /c/:id and /s/:token all render <Page id="chat">, so a conversation that gets
    its id mid-answer (/chat → /c/:id) keeps the same component and keeps streaming (Item 113). */
function Page({ id }: { id: keyof typeof PAGES }) {
  const P = PAGES[id];
  return (
    <Suspense fallback={<FrameOutline />}>
      <P />
    </Suspense>
  );
}

/** "/": the landing or the home, except a chat door (?q=, ?pin=, ?handoff=, ?ask=1) goes to /chat with its parameters. */
function Root() {
  const { search } = useLocation();
  if (isChatDoor(search)) return <Navigate to={`/chat${search}`} replace />;
  return <Page id="home" />;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <SelectedParcelProvider>
          <TrackPageView />
          {/* Right after a sign-in: "what best describes you", asked once. */}
          <SegmentQuestion />
          {/* The sign-in chooser and the sign-in/link result notice, once for the whole app (Item 121). */}
          <AuthOverlays />
          <Routes>
            <Route path="/" element={<Root />} />
            <Route path="/chat" element={<Page id="chat" />} />
            <Route path="/c/:id" element={<Page id="chat" />} />
            {/* A shared conversation, read only, on the chat page (Phase 10). */}
            <Route path="/s/:shareToken" element={<Page id="chat" />} />
            <Route path="/scorecard" element={<Page id="profile" />} />
            {/* /explore retired 2026-06-14: Discovery is a strict superset. Old links redirect. */}
            <Route path="/explore" element={<Navigate to="/discovery" replace />} />
            <Route path="/discovery" element={<Page id="discovery" />} />
            <Route path="/saved" element={<Page id="saved" />} />
            <Route path="/pricing" element={<Page id="pricing" />} />
            <Route path="/settings" element={<Page id="settings" />} />
            <Route path="/settings/:section" element={<Page id="settings" />} />
            <Route path="/about" element={<Page id="about" />} />
            <Route path="/privacy" element={<Page id="privacy" />} />
            <Route path="/admin" element={<Page id="admin" />} />
            <Route path="/admin/:section" element={<Page id="admin" />} />
            <Route path="*" element={<Page id="notFound" />} />
          </Routes>
          </SelectedParcelProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
)
