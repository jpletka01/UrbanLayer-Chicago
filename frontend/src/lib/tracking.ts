const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8001";

const SESSION_KEY = "ul_session_id";
const VISITOR_KEY = "ul_visitor_id";

function uuid(): string {
  return crypto.randomUUID();
}

function getSessionId(): string {
  let id = sessionStorage.getItem(SESSION_KEY);
  if (!id) {
    id = uuid();
    sessionStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export function getVisitorId(): string {
  let id = localStorage.getItem(VISITOR_KEY);
  if (!id) {
    id = uuid();
    localStorage.setItem(VISITOR_KEY, id);
  }
  return id;
}

const FIRST_TOUCH_KEY = "ul_first_touch";
const VISIT_TRACKED_KEY = "ul_visit_tracked";

interface Attribution {
  referrer: string | null;
  landing: string;
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
  utm_term: string | null;
  utm_content: string | null;
  ts: number;
}

function captureAttribution(): Attribution {
  const params = new URLSearchParams(window.location.search);
  return {
    referrer: document.referrer || null,
    landing: window.location.pathname + window.location.search,
    utm_source: params.get("utm_source"),
    utm_medium: params.get("utm_medium"),
    utm_campaign: params.get("utm_campaign"),
    utm_term: params.get("utm_term"),
    utm_content: params.get("utm_content"),
    ts: Date.now(),
  };
}

/** Once per session: fire visit_start with the current touch + the stored
 *  first touch, so channel attribution covers both new and returning visits. */
function trackVisitStart(): void {
  try {
    if (sessionStorage.getItem(VISIT_TRACKED_KEY)) return;
    sessionStorage.setItem(VISIT_TRACKED_KEY, "1");

    const current = captureAttribution();
    let firstTouch: Attribution | null = null;
    const stored = localStorage.getItem(FIRST_TOUCH_KEY);
    if (stored) {
      firstTouch = JSON.parse(stored) as Attribution;
    } else {
      firstTouch = current;
      localStorage.setItem(FIRST_TOUCH_KEY, JSON.stringify(current));
    }
    track("visit_start", { ...current, first_touch: firstTouch });
  } catch {
    // never throw
  }
}

interface TrackEvent {
  event_name: string;
  event_data?: Record<string, unknown> | null;
  session_id: string;
  visitor_id: string;
  page: string | null;
  address: string | null;
  timestamp: number;
}

let _queue: TrackEvent[] = [];
let _flushTimer: ReturnType<typeof setTimeout> | null = null;
let _address: string | null = null;

export function setAddress(addr: string | null): void {
  _address = addr;
}

function getCurrentPage(): string {
  return window.location.pathname;
}

export function track(
  eventName: string,
  data?: Record<string, unknown>,
): void {
  try {
    _queue.push({
      event_name: eventName,
      event_data: data ?? null,
      session_id: getSessionId(),
      visitor_id: getVisitorId(),
      page: getCurrentPage(),
      address: _address,
      timestamp: Date.now(),
    });
    if (!_flushTimer) {
      _flushTimer = setTimeout(flush, 30_000);
    }
  } catch {
    // never throw
  }
}

export function flush(): void {
  if (_flushTimer) {
    clearTimeout(_flushTimer);
    _flushTimer = null;
  }
  if (_queue.length === 0) return;

  const batch = _queue.splice(0, 50);
  const body = JSON.stringify({ events: batch });

  try {
    if (navigator.sendBeacon) {
      const sent = navigator.sendBeacon(
        `${API_BASE}/api/events`,
        new Blob([body], { type: "application/json" }),
      );
      if (!sent) {
        fetch(`${API_BASE}/api/events`, {
          method: "POST",
          body,
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          keepalive: true,
        }).catch(() => {});
      }
    } else {
      fetch(`${API_BASE}/api/events`, {
        method: "POST",
        body,
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        keepalive: true,
      }).catch(() => {});
    }
  } catch {
    // never throw
  }

  if (_queue.length > 0) {
    _flushTimer = setTimeout(flush, 30_000);
  }
}

export function initTracking(): void {
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });
  window.addEventListener("pagehide", flush);
  trackVisitStart();
}
