"""Current official rent for a parcel's area (WS4 PR2).

Three figures, each from the Census Bureau's ACS 5-year release, none combined with another:

* the community area's **overall** median gross rent, from the committed artifact
  ``ingestion/data/rent_by_area.json`` (summed tract bracket counts, built offline by
  ``ingestion.build_rent_artifact``; production never calls the Census API);
* the parcel's **tract** median by bedroom count (B25031), already in the tract request;
* when the tract's figure for a bedroom count is suppressed or too uncertain, the parcel's **PUMA** median for
  that count (B25031, one more Census Reporter request), named as the PUMA.

The Assessor's modeled apartment income (``assessor_model``, from ``assessor_model_by_area.json``) is a separate
series with its own coverage; it is never combined with the ACS figures above.

There is no community-area figure by bedroom count: the only table that crosses bedrooms with rent brackets
tops out at "$1,500 or more" (decision Item 33). Whether a figure is shown, faded or withheld is decided by
``provenance.confidence_state``; this module only uses the same rule to pick tract over PUMA.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import httpx

from backend.config import get_settings
from backend.models import AssessorModelRent, BedroomRent, CensusTractDemographics, CommunityAreaRent, RentCell, RentEvidence
from backend.retrieval.cache import TTLCache
from backend.retrieval.neighborhood.census_tract import _cv, rent_cells

log = logging.getLogger(__name__)

ARTIFACT_FILENAME = "rent_by_area.json"
ASSESSOR_FILENAME = "assessor_model_by_area.json"
# What the Profile shows. The studio and 4+ bedroom cells are published too, but the method proof only
# measured these three at PUMA level (20 of 20 standard).
BEDROOM_GROUPS = ("1_bedroom", "2_bedrooms", "3_bedrooms")

_puma_cache = TTLCache(ttl_seconds=86400, maxsize=64, name="census_puma_rent")
_lock = threading.Lock()
_artifact: dict | None = None
_assessor: dict | None = None


class RentArtifactError(RuntimeError):
    """The committed rent artifact is missing or unreadable: a broken deploy, never 'no rent here'."""


def artifact_path() -> Path:
    return get_settings().data_dir / ARTIFACT_FILENAME


def load_artifact() -> dict:
    """The artifact, read once per process. Raises ``RentArtifactError`` and caches nothing on failure."""
    global _artifact
    with _lock:
        if _artifact is None:
            try:
                data = json.loads(artifact_path().read_text(encoding="utf-8"))
                if not isinstance(data.get("community_areas"), dict) or not isinstance(data.get("tract_puma"), dict):
                    raise ValueError("missing community_areas / tract_puma")
            except (OSError, ValueError) as exc:
                raise RentArtifactError(f"{ARTIFACT_FILENAME} is unreadable: {exc}") from exc
            _artifact = data
        return _artifact


def load_assessor_artifact() -> dict:
    """The Assessor-model artifact, read once per process. Raises ``RentArtifactError``; caches nothing on failure."""
    global _assessor
    with _lock:
        if _assessor is None:
            path = get_settings().data_dir / ASSESSOR_FILENAME
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data.get("community_areas"), dict) or not (data.get("assessor") or {}).get("year"):
                    raise ValueError("missing community_areas / assessor.year")
            except (OSError, ValueError) as exc:
                raise RentArtifactError(f"{ASSESSOR_FILENAME} is unreadable: {exc}") from exc
            _assessor = data
        return _assessor


def reset_artifact() -> None:
    """Forget the loaded artifacts (tests)."""
    global _artifact, _assessor
    with _lock:
        _artifact = _assessor = None


def community_area_rent(community_area: int) -> CommunityAreaRent | None:
    """The community area's overall median gross rent; None when the artifact has no row for the area."""
    art = load_artifact()
    row = art["community_areas"].get(str(community_area))
    if row is None:
        return None
    acs, method = art.get("acs") or {}, art.get("method") or {}
    median, moe = row.get("median"), row.get("moe")
    return CommunityAreaRent(
        community_area=community_area, households=int(row.get("households") or 0), median=median, moe=moe,
        cv=_cv(median, moe), top_coded=bool(row.get("top_coded")),
        moe_method=method.get("key") or "acs_handbook_median", design_factor=method.get("design_factor"),
        acs_period=acs.get("period"), acs_release=acs.get("release"), period_end=acs.get("period_end"),
    )


def assessor_model_rent(community_area: int) -> AssessorModelRent | None:
    """The Assessor's modeled apartment income for a community area (its own series, never merged with the ACS).

    The artifact lists every area the Assessor models apartments in; an area with a household count but no row
    (Fuller Park) is a real finding and comes back with zero buildings. None only for an area neither artifact knows."""
    art = load_assessor_artifact()
    meta = art["assessor"]
    row = art["community_areas"].get(str(community_area))
    if row is None:
        if str(community_area) not in load_artifact()["community_areas"]:
            return None
        row = {}
    households = row.get("households")
    if households is None:
        households = (load_artifact()["community_areas"].get(str(community_area)) or {}).get("households")
    units = int(row.get("units") or 0)
    return AssessorModelRent(
        community_area=community_area, buildings=int(row.get("buildings") or 0), priced=int(row.get("priced") or 0),
        units=units, households=households, coverage=round(units / households, 4) if households else None,
        median_per_unit_month=row.get("median_pgi_per_unit_month"), year=str(meta["year"]),
        cycle=meta.get("cycle") or "city reassessment", as_of=meta.get("as_of") or f"{meta['year']}-12-31",
        dataset=meta.get("dataset") or "csik-bsws",
    )


def puma_for_tract(tract_fips: str) -> str | None:
    """The 7-character PUMA geoid (state + PUMA, as Parcel Universe writes it) holding a tract."""
    return load_artifact()["tract_puma"].get(tract_fips)


def _is_standard(cell: RentCell | None) -> bool:
    """True when a published cell passes the confidence standard's CV rule, judged where the rule lives."""
    if cell is None or cell.estimate is None or cell.cv is None:
        return False
    from backend.provenance import confidence_state

    return confidence_state({"precision": {"cv": cell.cv}})[0] == "standard"


async def fetch_puma_rent(
    puma_geoid: str, release_id: str, *, client: httpx.AsyncClient | None = None,
) -> tuple[str | None, dict[str, RentCell]]:
    """``(PUMA name, bedroom cells)`` from the given ACS 5-year release.

    The release must be named: Census Reporter's ``latest`` answers a PUMA from the 1-year release (2024 only,
    much wider margins) because PUMAs exist there, while tracts only exist in the 5-year. A response from any
    other release is an error, never a figure."""
    key = f"puma_rent:{release_id}:{puma_geoid}"
    cached = _puma_cache.get(key)
    if cached is not None:
        return cached
    geo_id = f"79500US{puma_geoid}"
    url = f"{get_settings().census_reporter_base}/data/show/{release_id}"
    owns = client is None
    if owns:
        client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    try:
        resp = await client.get(url, params={"table_ids": "B25031", "geo_ids": geo_id})
        resp.raise_for_status()
        payload = resp.json()
        got = (payload.get("release") or {}).get("id")
        if got != release_id:
            raise RuntimeError(f"Census Reporter answered release {got!r}, not {release_id!r}")
        data = (payload.get("data") or {}).get(geo_id)
        if not data:
            raise RuntimeError(f"Census Reporter returned no B25031 data for PUMA {puma_geoid}")
        name = ((payload.get("geography") or {}).get(geo_id) or {}).get("name")
        result = (name, rent_cells(data))
        _puma_cache.set(key, result)
        return result
    finally:
        if owns:
            await client.aclose()


def select_bedrooms(
    tract: CensusTractDemographics | None,
    puma_cells: dict[str, RentCell] | None,
    puma_name: str | None,
    puma_geoid: str | None,
) -> list[BedroomRent]:
    """One entry per bedroom count: the tract's figure when it passes the CV rule, otherwise the PUMA's.

    When neither passes, the entry keeps the tract's own cell (so confidence can withhold it with its reason)
    unless the tract has none at all and the PUMA does (a PUMA figure is better named than a blank)."""
    out: list[BedroomRent] = []
    for group in BEDROOM_GROUPS:
        t_cell = (tract.rent_by_bedroom.get(group) if tract else None)
        p_cell = (puma_cells or {}).get(group)
        if _is_standard(t_cell) or (p_cell is None and t_cell is not None):
            out.append(BedroomRent(
                bedrooms=group, scope="tract", geography=tract.tract_name if tract else None,
                geoid=tract.tract_fips if tract else None,
                estimate=t_cell.estimate, moe=t_cell.moe, cv=t_cell.cv,
                tract_fallback=None if _is_standard(t_cell) else "suppressed" if t_cell.estimate is None else "low_confidence"))
        elif p_cell is not None:
            reason = "suppressed" if t_cell is None or t_cell.estimate is None else "low_confidence"
            out.append(BedroomRent(
                bedrooms=group, scope="puma", geography=puma_name, geoid=puma_geoid,
                estimate=p_cell.estimate, moe=p_cell.moe, cv=p_cell.cv, tract_fallback=reason))
    return out


async def rent_evidence(
    community_area: int | None,
    tract: CensusTractDemographics | None,
    *,
    client: httpx.AsyncClient | None = None,
) -> RentEvidence | None:
    """Everything the Profile says about current official rent for this parcel.

    A part that cannot be fetched is named in ``unchecked`` and left out; it is never reported as absent.
    None when there is nothing to say (no community area, no tract)."""
    if community_area is None and tract is None:
        return None
    ev = RentEvidence()
    try:
        ev.community_area = community_area_rent(community_area) if community_area is not None else None
    except RentArtifactError as exc:
        log.error("%s", exc)
        ev.unchecked.append("community_area_rent")
    if ev.community_area is not None:
        ev.acs_period, ev.acs_release = ev.community_area.acs_period, ev.community_area.acs_release
    try:
        ev.assessor_model = assessor_model_rent(community_area) if community_area is not None else None
    except RentArtifactError as exc:
        log.error("%s", exc)
        ev.unchecked.append("assessor_model")

    if tract is None:
        ev.unchecked.append("tract_rent")
        return ev
    ev.tract_name = tract.tract_name
    ev.acs_period = tract.acs_period or ev.acs_period
    ev.acs_release = tract.acs_release or ev.acs_release
    puma_cells: dict[str, RentCell] | None = None
    needs_puma = not all(_is_standard(tract.rent_by_bedroom.get(g)) for g in BEDROOM_GROUPS)
    if needs_puma:
        try:
            ev.puma_geoid = puma_for_tract(tract.tract_fips)
            release = tract.acs_release or (ev.community_area.acs_release if ev.community_area else None)
            if ev.puma_geoid and release:
                ev.puma_name, puma_cells = await fetch_puma_rent(ev.puma_geoid, release, client=client)
            elif not ev.puma_geoid:
                ev.unchecked.append("puma_rent")
        except (RentArtifactError, httpx.HTTPError, RuntimeError, ValueError) as exc:
            log.warning("PUMA rent failed for tract %s: %s", tract.tract_fips, exc)
            ev.unchecked.append("puma_rent")
    ev.bedrooms = select_bedrooms(tract, puma_cells, ev.puma_name, ev.puma_geoid)
    return ev
