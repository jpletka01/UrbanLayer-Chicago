"""What changed since an answer or a report was made (WS6 M9, plan §4.4).

``compare(old, current)`` is pure: it takes the snapshot an answer kept (``facts.snapshot``) and a snapshot of
today's facts for the same place, and lists the *material* changes. ``changes_for(old)`` fetches today's facts
(the same zoning and overlay lookups the Profile uses, sharing their caches, plus local files; **no model
call**), caches them per parcel per day, and compares.

Material, and nothing else: the district; the overlays that carry a rule (planned development, landmark,
historic district, pedestrian street, TOD, ADU area, ARO zone, special district, lakefront, flood); a bulk
standard of the same district; a Title 17 amendment touching what the answer cited (before or after the
answer); a rezoning or landmark designation passed that lists the parcel; a code text refresh that changed a
cited section; a recorded source correction. Crime, 311, permits, comps and the like are never flagged.

**Never "no change" for something we could not check.** A district or overlay lookup that fails makes no claim
about that fact and says "couldn't re-check"; it never reads as unchanged.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

CORRECTIONS_FILE = Path(__file__).resolve().parent / "corrections.json"
CODE_CHANGES_FILE = Path(__file__).resolve().parent.parent / "code_changes.json"

# An answer younger than this has nothing to compare against yet: it says "Answered today".
MIN_AGE = timedelta(hours=24)
# Distinct parcels re-checked per conversation (the newest first); the rest say nothing.
MAX_PARCELS_PER_CONVERSATION = 3

# Overlay layers whose presence changes a rule or a verdict. Not here: special service areas (a funding
# district) and anything the map does not carry as a layer.
MATERIAL_OVERLAYS = frozenset({
    "planned_development", "lakefront_protection", "pedestrian_street", "landmark_building", "historic_district",
    "national_register", "special_district", "pmd_subarea", "tod_cta", "tod_metra", "adu_area", "aro_zone",
    "fema_floodplain",
})
STANDARD_KEYS = ("far", "max_height", "min_lot_area_per_unit")

KINDS = ("district", "overlay", "standards", "amendment", "map_amendment", "designation", "text_refresh", "correction")


# --- small readers ---------------------------------------------------------------------------------------

def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        log.warning("Unreadable file: %s", path)
        return None


def load_corrections() -> list[dict]:
    data = _load(CORRECTIONS_FILE)
    return list((data or {}).get("corrections") or []) if isinstance(data, dict) else []


def load_refreshes() -> list[dict]:
    data = _load(CODE_CHANGES_FILE)
    return list((data or {}).get("refreshes") or []) if isinstance(data, dict) else []


def _norm_zone(z: str | None) -> str:
    return (z or "").strip().upper().replace(" ", "")


def _get(snap: dict, path: str) -> Any:
    cur: Any = snap
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _matches(snap: dict, applies_if: dict) -> bool:
    for path, want in (applies_if or {}).items():
        have = _get(snap, path)
        if isinstance(want, dict):
            if "in" in want and _norm_zone(str(have)) not in {_norm_zone(w) for w in want["in"]}:
                return False
            if "prefix" in want and not str(have or "").upper().startswith(str(want["prefix"]).upper()):
                return False
        elif have != want:
            return False
    return bool(applies_if)


def answered_day(snap: dict) -> str | None:
    return (snap.get("answered_at") or "")[:10] or None


# --- the old snapshot, when none was stored --------------------------------------------------------------

def reconstruct(context: dict | None, plan: dict | None, created_at_ms: int | None) -> dict | None:
    """A best-effort snapshot of an answer stored before snapshots (or before they kept the point), from its
    ``context_json`` and ``plan_json``. Marked ``reconstructed``. The code text every such answer used is the
    one in force before the first recorded refresh. None when the context is not of a parcel."""
    if not context or not created_at_ms:
        return None  # an answer with no date can't be placed against today's facts
    try:
        from backend.data_health import facts
        from backend.models import ContextObject

        ctx = ContextObject.model_validate(context)
        answered = datetime.fromtimestamp(created_at_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        loc = (plan or {}).get("location") or {}
        snap = facts.snapshot(ctx, answered_at=answered, lat=loc.get("resolved_lat"), lon=loc.get("resolved_lon"))
    except Exception:
        log.warning("Could not reconstruct a snapshot", exc_info=True)
        return None
    if not facts.resolved_parcel(snap):
        return None
    snap["reconstructed"] = True
    # ``ContextObject.code_vintage`` is computed from today's files, so a rebuilt snapshot would claim the
    # CURRENT text. An answer given before a recorded refresh was applied used the text before it.
    code = snap.setdefault("code", {})
    refreshes = sorted(load_refreshes(), key=lambda r: r.get("applied_at") or "")
    first = refreshes[0] if refreshes else None
    if first and first.get("from") and snap.get("answered_at") and snap["answered_at"] < (first.get("applied_at") or ""):
        code["current_through"] = first["from"]
    return snap


def with_point(snap: dict | None, plan: dict | None, fallback: tuple[float, float] | None = None) -> dict | None:
    """The snapshot with the point it was made at: stored snapshots from before M9 kept none, the message's plan
    did. ``fallback`` is the render row's own point for a report."""
    if snap is None or (snap.get("lat") is not None and snap.get("lon") is not None):
        return snap
    loc = (plan or {}).get("location") or {}
    lat, lon = loc.get("resolved_lat"), loc.get("resolved_lon")
    if lat is None or lon is None:
        lat, lon = fallback if fallback else (None, None)
    return {**snap, "lat": lat, "lon": lon}


# --- today's facts ---------------------------------------------------------------------------------------

def check_key(snap: dict) -> str | None:
    if snap.get("lat") is None or snap.get("lon") is None:
        return None
    return f"{snap.get('pin') or '-'}|{round(float(snap['lat']), 5)},{round(float(snap['lon']), 5)}"


async def current_facts(old: dict) -> dict | None:
    """A snapshot of today's facts at the old snapshot's point, built from the Profile's own lookups, plus
    ``checked`` (which facts could be read) and ``passed_detail`` (the passed ordinances, with their links).
    None when the old snapshot has no point to look at."""
    import asyncio

    from backend.data_health import facts
    from backend.models import ContextObject, RegulatorySummary, ZoningSummary
    from backend.retrieval.regulatory import regulatory_domain
    from backend.retrieval.regulatory.overlays import OVERLAY_LAYERS
    from backend.retrieval.zoning import lookup_zoning
    from backend.retrieval.zoning_definitions import get_zone_definition

    if old.get("lat") is None or old.get("lon") is None:
        return None
    lat, lon = float(old["lat"]), float(old["lon"])
    zoning_raw, reg = await asyncio.gather(
        lookup_zoning(lat, lon), regulatory_domain(lat, lon, workflow="site_due_diligence"), return_exceptions=True,
    )
    zoning_ok = isinstance(zoning_raw, dict) and bool(zoning_raw.get("zone_class"))
    if isinstance(reg, Exception):
        reg = RegulatorySummary(unchecked_overlays=[v["type"] for v in OVERLAY_LAYERS.values()])
    zoning = None
    if zoning_ok:
        zoning = ZoningSummary(**{k: zoning_raw.get(k) for k in (
            "zone_class", "zone_type", "ordinance_num", "application_num", "ordinance_date", "map_updated", "clerk_url")})
    ctx = ContextObject(
        resolved_address=old.get("address"), parcel_pin=old.get("pin"), parcel_resolution=None,
        parcel_zoning=zoning, regulatory=reg,
    )
    zd = None
    if zoning is not None:
        from dataclasses import asdict

        zd = asdict(get_zone_definition(zoning.zone_class))
    snap = facts.snapshot(ctx, zone_definition=zd, lat=lat, lon=lon, address=old.get("address"), pin=old.get("pin"))
    if zoning is not None:
        snap["zoning"]["clerk_url"] = zoning.clerk_url
    # The City's own wording of each overlay's name, to show on an "added" line (the snapshot keeps names normalized).
    snap["overlay_labels"] = {f"{o.layer_type}|{facts.normalize_name(o.name)}": o.name for o in (reg.overlays or []) if o.name}
    snap["checked"] = {"zoning": zoning_ok, "unchecked_overlays": list(reg.unchecked_overlays or [])}
    snap["passed_detail"] = {
        "rezonings": list(ctx.passed_not_on_map or []),
        "landmark_designations": list(ctx.passed_landmark_designations or []),
    }
    return snap


# --- the comparison --------------------------------------------------------------------------------------

def _amendments(old: dict) -> list[dict]:
    from backend.legislation import currency
    from backend.legislation.amendments import sections_overlap

    code = old.get("code") or {}
    through = code.get("current_through")
    cited = [*(code.get("cited_sections") or []), *(code.get("bulk_sections") or [])]
    if not through or not cited:
        return []
    try:
        day = date.fromisoformat(through)
    except ValueError:
        return []
    answered = answered_day(old) or ""
    out = []
    for a in currency.amendments_since(day, scope=currency.ALL_SCOPES):
        hit = [s for s in a.get("sections") or [] if any(sections_overlap(s, c) for c in cited)]
        if not hit:
            continue
        out.append({
            "kind": "amendment", "phase": "after_answer" if (a.get("passed_on") or "") > answered else "before_answer",
            "record": a.get("record"), "title": a.get("title"), "passed_on": a.get("passed_on"), "url": a.get("url"),
            "sections": hit,
        })
    return out


def _text_refresh(old: dict) -> list[dict]:
    from backend.legislation.amendments import sections_overlap

    code = old.get("code") or {}
    through = code.get("current_through")
    cited = [*(code.get("cited_sections") or []), *(code.get("bulk_sections") or [])]
    if not through or not cited:
        return []
    out = []
    for r in load_refreshes():
        if not r.get("to") or r["to"] <= through:
            continue
        changed = [c for c in dict.fromkeys(cited)
                   if any(sections_overlap(c, s) for s in [*(r.get("modified") or []), *(r.get("removed") or [])])]
        if changed:
            out.append({"kind": "text_refresh", "current_through": r["to"], "sections": changed})
    return out


def compare(old: dict, cur: dict | None) -> dict:
    """The material changes from ``old`` to ``cur`` (today's facts, or None when they could not be read).

    Returns ``{"status": "changes" | "none" | "partial" | "unavailable", "changes": [...], "unchecked": [...]}``.
    ``partial`` = nothing changed among the facts we could read, but some could not be read; ``unavailable``
    = today's facts could not be read at all."""
    changes: list[dict] = []
    unchecked: list[str] = []

    if cur is None:
        unchecked.append("everything")
        # The parts that need no lookup still hold: amendments, text refreshes, corrections.
        changes += _amendments(old) + _text_refresh(old)
    else:
        checked = cur.get("checked") or {}
        old_zone, new_zone = (old.get("zoning") or {}), (cur.get("zoning") or {})
        if not checked.get("zoning", cur.get("zoning") is not None):
            unchecked.append("district")
        elif old_zone.get("zone_class") and new_zone.get("zone_class") and _norm_zone(old_zone["zone_class"]) != _norm_zone(new_zone["zone_class"]):
            changes.append({
                "kind": "district", "old": old_zone["zone_class"], "new": new_zone["zone_class"],
                "record": new_zone.get("ordinance_num"), "passed_on": new_zone.get("ordinance_date"),
                "url": new_zone.get("clerk_url"),
            })

        skip = set(old.get("unchecked_overlays") or []) | set((checked.get("unchecked_overlays")) or [])
        unchecked += sorted(f"overlay:{t}" for t in set(checked.get("unchecked_overlays") or []) & MATERIAL_OVERLAYS)
        old_ov = {(t, n) for t, n in old.get("overlays") or [] if t in MATERIAL_OVERLAYS and t not in skip}
        new_ov = {(t, n) for t, n in cur.get("overlays") or [] if t in MATERIAL_OVERLAYS and t not in skip}
        labels = cur.get("overlay_labels") or {}
        for t, n in sorted(new_ov - old_ov):
            changes.append({"kind": "overlay", "change": "added", "layer": t, "name": labels.get(f"{t}|{n}")})
        for t, n in sorted(old_ov - new_ov):
            changes.append({"kind": "overlay", "change": "removed", "layer": t, "name": None})

        if old_zone.get("zone_class") and _norm_zone(old_zone["zone_class"]) == _norm_zone(new_zone.get("zone_class")):
            os_, ns = old.get("standards") or {}, cur.get("standards") or {}
            for k in STANDARD_KEYS:
                if os_.get(k) is not None and ns.get(k) is not None and str(os_[k]) != str(ns[k]):
                    changes.append({"kind": "standards", "field": k, "old": os_[k], "new": ns[k], "zone_class": new_zone.get("zone_class")})

        detail = cur.get("passed_detail") or {}
        for kind, key, field in (("map_amendment", "rezonings", "rezonings"), ("designation", "landmark_designations", "landmark_designations")):
            seen = set((old.get("passed") or {}).get(field) or [])
            for h in detail.get(key) or []:
                if h.get("record") not in seen:
                    changes.append({"kind": kind, "record": h.get("record"), "passed_on": h.get("passed_on"),
                                    "url": h.get("url"), "name": h.get("name")})
        changes += _amendments(old) + _text_refresh(old)

    answered = answered_day(old) or ""
    for c in load_corrections():
        if c.get("date", "") > answered and _matches(old, c.get("applies_if") or {}):
            changes.append({"kind": "correction", "id": c["id"], "date": c["date"], "summary": c.get("summary"), "commit": c.get("commit")})

    status = "changes" if changes else ("unavailable" if cur is None else ("partial" if unchecked else "none"))
    return {"status": status, "changes": changes, "unchecked": unchecked}


# --- the whole check, cached per parcel and day ----------------------------------------------------------

def _too_soon(old: dict, now: datetime) -> bool:
    try:
        t = datetime.fromisoformat((old.get("answered_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return False
    return now - t < MIN_AGE


async def changes_for(old: dict | None, *, now: datetime | None = None) -> dict:
    """The "since then" result for one snapshot: ``{"answered_on", "status", "changes", "unchecked",
    "reconstructed"}`` with status ``changes | none | partial | unavailable | too_soon | no_parcel``. Today's
    facts are looked up once per (parcel, day) and kept in ``fact_checks``, so a crowd opening one shared
    link costs one lookup. A lookup that could not read everything is not kept."""
    from backend import db

    now = now or datetime.now(timezone.utc)
    if not old:
        return {"status": "no_parcel", "changes": [], "unchecked": []}
    base = {"answered_on": answered_day(old), "reconstructed": bool(old.get("reconstructed"))}
    if _too_soon(old, now):
        return {**base, "status": "too_soon", "changes": [], "unchecked": []}
    key = check_key(old)
    cur = None
    if key:
        day = now.strftime("%Y-%m-%d")
        cur = await db.get_fact_check(key, day)
        if cur is None:
            try:
                cur = await current_facts(old)
            except Exception:
                log.warning("Re-check failed for %s", key, exc_info=True)
                cur = None
            checked = (cur or {}).get("checked") or {}
            if cur is not None and checked.get("zoning") and not checked.get("unchecked_overlays"):
                await db.put_fact_check(key, day, cur)
    return {**base, **compare(old, cur)}


async def conversation_changes(conv_id: str, *, now: datetime | None = None) -> dict:
    """``{"notes": {message_index: result}}`` for the parcel answers of a conversation. A snapshot is the stored
    one, or rebuilt from the message's context and plan (``reconstructed``). At most
    ``MAX_PARCELS_PER_CONVERSATION`` distinct parcels are re-checked, newest answer first; an answer about
    another parcel gets ``status: "skipped"`` (it still has its date). Messages with no parcel get no note."""
    from backend import db

    now = now or datetime.now(timezone.utc)
    notes: dict[str, dict] = {}
    seen: list[str] = []
    for m in reversed(await db.get_message_facts(conv_id)):
        if m["role"] != "assistant":
            continue
        snap = with_point(m["facts"], m["plan"]) if m["facts"] else reconstruct(m["context"], m["plan"], m["created_at"])
        if snap is None:
            continue
        key = check_key(snap) or f"pin:{snap.get('pin')}"
        if key not in seen:
            if len(seen) >= MAX_PARCELS_PER_CONVERSATION:
                notes[str(m["index"])] = {"answered_on": answered_day(snap), "status": "skipped", "changes": [], "unchecked": [],
                                          "reconstructed": bool(snap.get("reconstructed"))}
                continue
            seen.append(key)
        notes[str(m["index"])] = await changes_for(snap, now=now)
    return {"notes": notes}


async def purchase_changes(user_id: str, *, now: datetime | None = None) -> dict[int, dict]:
    """``{purchase_id: result}`` comparing each purchase's original render with today's facts."""
    from backend import db

    out: dict[int, dict] = {}
    for pid, snap in (await db.get_purchase_original_facts(user_id)).items():
        out[pid] = await changes_for(snap, now=now)
    return out
