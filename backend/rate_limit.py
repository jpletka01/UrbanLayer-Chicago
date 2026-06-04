"""Per-user rate limiting + daily API budget cap.

Limits are enforced only on the /chat endpoint. Uses in-memory sliding
window counters keyed by user_id (or IP for anonymous users).
"""

from __future__ import annotations

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


def _get_client_key(request: Request, user: dict | None) -> str:
    if user and user.get("id") != "dev":
        return f"user:{user['id']}"
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"ip:{ip}"


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
        "SELECT model, SUM(input_tokens) as inp, SUM(output_tokens) as out "
        "FROM llm_calls WHERE created_at >= ? GROUP BY model",
        (cutoff_ms,),
    )
    rows = await cur.fetchall()

    total_cost = sum(
        estimate_cost(row["model"], row["inp"] or 0, row["out"] or 0)
        for row in rows
    )

    if total_cost >= budget:
        raise HTTPException(
            status_code=503,
            detail="Daily API budget reached. Service will resume tomorrow.",
        )
