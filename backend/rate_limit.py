"""Per-user rate limiting + daily API budget cap.

Limits are enforced only on the /chat endpoint. Uses in-memory sliding
window counters keyed by user_id (or IP for anonymous users).
"""

from __future__ import annotations

import ipaddress
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import HTTPException, Request

from backend.auth import get_current_user

log = logging.getLogger(__name__)


def _tier_limits() -> dict[str, tuple[int, int]]:
    return {
        "anonymous": (
            int(os.environ.get("RATE_LIMIT_ANON_DAY", "3")),
            int(os.environ.get("RATE_LIMIT_ANON_HOUR", "3")),
        ),
        "free": (25, 10),
        "premium": (100, 30),
        "admin": (0, 0),
    }


@dataclass
class _UserWindow:
    timestamps: list[float] = field(default_factory=list)

    def count_since(self, cutoff: float) -> int:
        self.timestamps = [t for t in self.timestamps if t >= cutoff]
        return len(self.timestamps)

    def record(self) -> None:
        self.timestamps.append(time.time())


_windows: dict[str, _UserWindow] = defaultdict(_UserWindow)


def clear_rate_limits() -> None:
    """Clear all in-memory rate limit state. Used by tests."""
    _windows.clear()


# Peers allowed to tell us the client's address via X-Real-IP: loopback and the
# private ranges Docker assigns to the compose network. In production the backend
# port is not published, so the only peer that can reach it is the nginx
# container, which overwrites X-Real-IP with the address it derived from
# Cloudflare's CF-Connecting-IP (trusted only from Cloudflare's ranges — see
# frontend/nginx.prod.conf).
_TRUSTED_PROXY_NETS = tuple(
    ipaddress.ip_network(net)
    for net in ("127.0.0.0/8", "::1/128", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def client_ip(request: Request) -> str:
    """The caller's IP address.

    X-Forwarded-For is never read: its leftmost entry is whatever the client sent,
    so keying on it let anyone mint a fresh anonymous identity per request.
    X-Real-IP is honoured only when the direct peer is our own reverse proxy.
    """
    peer = request.client.host if request.client else ""
    peer_addr = _parse_ip(peer)
    if peer_addr is not None and any(peer_addr in net for net in _TRUSTED_PROXY_NETS):
        real = _parse_ip(request.headers.get("x-real-ip", ""))
        if real is not None:
            return str(real)
    return peer or "unknown"


def _ip_bucket(ip: str) -> str:
    """Rate-limit bucket for an IP. IPv6 is keyed by /64 — a single subscriber
    typically controls a whole /64, so per-address keys would be trivially rotated."""
    addr = _parse_ip(ip)
    if addr is not None and addr.version == 6:
        return str(ipaddress.ip_network(f"{addr}/64", strict=False))
    return ip


def _get_client_key(request: Request, user: dict | None) -> str:
    if user and user.get("id") != "dev":
        return f"user:{user['id']}"
    return f"ip:{_ip_bucket(client_ip(request))}"


def _get_tier(user: dict | None) -> str:
    if not user or user.get("id") == "dev":
        return "anonymous"
    return user.get("tier", "free")


async def check_rate_limit(request: Request) -> dict | None:
    """Check rate limits for the current request. Returns the user dict.

    Raises HTTPException(429) if the user has exceeded their limits.
    """
    try:
        user = await get_current_user(request)
    except RuntimeError:
        user = None
    tier = _get_tier(user)
    day_limit, hour_limit = _tier_limits().get(tier, (3, 3))

    if day_limit == 0 and hour_limit == 0:
        return user

    key = _get_client_key(request, user)
    window = _windows[key]

    now = time.time()
    day_count = window.count_since(now - 86400)
    hour_count = window.count_since(now - 3600)

    if day_limit and day_count >= day_limit:
        retry_after = 86400 - int(now - min(window.timestamps)) if window.timestamps else 86400
        raise HTTPException(
            status_code=429,
            detail=f"Daily query limit reached ({day_limit}/day). Sign in for higher limits."
            if tier == "anonymous"
            else f"Daily query limit reached ({day_limit}/day).",
            headers={"Retry-After": str(max(retry_after, 60))},
        )

    if hour_limit and hour_count >= hour_limit:
        retry_after = 3600 - int(now - min(t for t in window.timestamps if t >= now - 3600)) if window.timestamps else 3600
        raise HTTPException(
            status_code=429,
            detail=f"Hourly query limit reached ({hour_limit}/hour).",
            headers={"Retry-After": str(max(retry_after, 60))},
        )

    window.record()
    return user


async def check_daily_budget() -> None:
    """Check if today's API spend exceeds the daily budget cap.

    Uses the llm_calls table to sum today's estimated costs.
    """
    import os
    budget_str = os.environ.get("DAILY_API_BUDGET_USD", "5.00")
    try:
        budget = float(budget_str)
    except ValueError:
        return

    from backend import db as _db
    from backend.llm import estimate_cost

    try:
        conn = _db._get_db()
    except RuntimeError:
        return
    import datetime
    midnight = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_ms = int(midnight.timestamp() * 1000)

    cur = await conn.execute(
        "SELECT model, SUM(input_tokens) as inp, SUM(output_tokens) as out, "
        "SUM(cache_read_tokens) as cache_read, SUM(cache_create_tokens) as cache_write "
        "FROM llm_calls WHERE created_at >= ? GROUP BY model",
        (cutoff_ms,),
    )
    rows = await cur.fetchall()

    total_cost = sum(
        estimate_cost(
            row["model"], row["inp"] or 0, row["out"] or 0,
            row["cache_read"] or 0, row["cache_write"] or 0,
        )
        for row in rows
    )

    if total_cost >= budget:
        raise HTTPException(
            status_code=503,
            detail="Daily API budget reached. Service will resume tomorrow.",
        )
