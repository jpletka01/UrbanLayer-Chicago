"""PTAXSIM-based property tax estimation by PIN.

Uses the CCAO's PTAXSIM SQLite database (downloaded separately via
``scripts/download_ptaxsim.py``) to compute line-item tax breakdowns.
The database contains pre-computed ``tax_bill_total`` per PIN per year
and agency-level rates per tax code, so the breakdown is a proportional
allocation of the total across taxing agencies.
"""

import asyncio
import logging

import aiosqlite

from backend.config import get_settings

log = logging.getLogger(__name__)

_conn: aiosqlite.Connection | None = None
_lock = asyncio.Lock()

# ptaxsim `pin` table exemption columns -> human-readable kind. Ordered dict:
# iteration order drives both the SELECT and the output list.
_EXEMPTION_KINDS: dict[str, str] = {
    "exe_homeowner": "Homeowner",
    "exe_senior": "Senior Citizen",
    "exe_freeze": "Senior Freeze",
    "exe_longtime_homeowner": "Longtime Homeowner",
    "exe_disabled": "Persons with Disabilities",
    "exe_vet_returning": "Returning Veteran",
    "exe_vet_dis_lt50": "Disabled Veteran (<50%)",
    "exe_vet_dis_50_69": "Disabled Veteran (50-69%)",
    "exe_vet_dis_ge70": "Disabled Veteran (70%+)",
    "exe_vet_dis_100": "Disabled Veteran (100%)",
    "exe_wwii": "WWII Veteran",
    "exe_abate": "Abatement",
}


async def _get_conn() -> aiosqlite.Connection:
    global _conn
    async with _lock:
        if _conn is None:
            settings = get_settings()
            _conn = await aiosqlite.connect(str(settings.ptaxsim_db_path))
            _conn.row_factory = aiosqlite.Row
        return _conn


async def close() -> None:
    global _conn
    async with _lock:
        if _conn is not None:
            await _conn.close()
            _conn = None


async def estimate_tax(year: int, pin14: str) -> dict | None:
    """Compute line-item property tax breakdown for a PIN.

    Returns a dict with year, pin, tax_code, tax_bill_total,
    assessed_value, exemptions, and line_items (top 15 agencies),
    or None if the PIN is not found.
    """
    settings = get_settings()
    if not settings.ptaxsim_enabled:
        return None
    if not settings.ptaxsim_db_path.exists():
        return None

    conn = await _get_conn()

    pin_clean = pin14.replace("-", "")

    # Select the most recent available year at or before the requested one. The
    # PTAXSIM DB lags ~1 year behind the calendar (e.g. max year 2024 in 2026), so
    # a fixed ``today-1`` would 404 every report; this clamps gracefully per-PIN.
    exe_cols = ", ".join(_EXEMPTION_KINDS)
    async with conn.execute(
        f"SELECT year, tax_code_num, tax_bill_total, av_clerk, {exe_cols} "
        "FROM pin WHERE pin = ? AND year <= ? ORDER BY year DESC LIMIT 1",
        (pin_clean, year),
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        return None

    data_year = row["year"]
    tax_code = row["tax_code_num"]
    tax_bill_total = row["tax_bill_total"]
    av_clerk = row["av_clerk"]
    # NOTE semantics: exe_* values are EAV DEDUCTIONS (equalized assessed value
    # removed before rates apply), NOT dollars off the bill. Present them as
    # "reduces taxable value", never as savings.
    exemptions = [
        {"kind": _EXEMPTION_KINDS[col], "eav_reduction": row[col]}
        for col in _EXEMPTION_KINDS
        if row[col] and row[col] > 0
    ]
    total_exe = sum(e["eav_reduction"] for e in exemptions)

    async with conn.execute(
        "SELECT ai.agency_name, tc.agency_rate, tc.tax_code_rate "
        "FROM tax_code tc "
        "JOIN agency_info ai ON tc.agency_num = ai.agency_num "
        "WHERE tc.year = ? AND tc.tax_code_num = ? "
        "ORDER BY tc.agency_rate DESC",
        (data_year, tax_code),
    ) as cursor:
        agencies = await cursor.fetchall()

    line_items = []
    for ag in agencies:
        rate = ag["agency_rate"]
        code_rate = ag["tax_code_rate"]
        amount = tax_bill_total * (rate / code_rate) if code_rate > 0 else 0.0
        line_items.append({
            "agency": ag["agency_name"],
            "rate": round(rate, 6),
            "amount": round(amount, 2),
        })

    return {
        "year": data_year,
        "pin": pin_clean,
        "tax_code": tax_code,
        "tax_bill_total": round(tax_bill_total, 2),
        "assessed_value": av_clerk,
        "total_exemptions": total_exe,
        "exemptions": exemptions,
        "line_items": line_items[:15],
    }
