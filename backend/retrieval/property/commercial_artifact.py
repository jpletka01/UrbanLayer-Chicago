"""The committed Commercial Valuation building areas (``ingestion/data/commercial_bldg_by_pin.json.gz``).

WS8 Phase 1 (decision Item 39).  Built offline by ``ingestion.build_commercial_bldg_artifact`` from the Assessor's
latest city-wide reassessment; read here with no network.  The capacity map uses it for the parcels the Discovery
index has no building area for (commercial and large multifamily buildings).

``building_area(pin14)`` answers one of three things, never a guess:

* ``UnitArea``: the unit's building area belongs to this lot: every member PIN is on the same PIN10 (a single-PIN
  unit, or a building whose PIN14s share one base parcel).
* ``MultiPinMember``: the area on file is the total of a complex spanning several PIN10s.  It describes no single
  lot, keypin included: shown against one lot it reads as a FAR several times too high (the Profile's "FAR 10.07"
  case).  Also returned when a PIN sits in more than one unit, since then no unit speaks for it.
* ``None``: the PIN is in no economic unit, or its unit carries no area.

A missing or unreadable artifact raises ``CapacityArtifactError``: "could not check" is never "no building".
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ARTIFACT_PATH = Path(__file__).resolve().parents[3] / "ingestion" / "data" / "commercial_bldg_by_pin.json.gz"
SOURCE_ID = "artifact.commercial_bldg_by_pin"


class CapacityArtifactError(RuntimeError):
    """The Commercial Valuation artifact is missing or unreadable."""


@dataclass(frozen=True)
class UnitArea:
    bldg_sqft: float
    unit_pins: tuple[str, ...]
    year: str
    source: str = SOURCE_ID


@dataclass(frozen=True)
class MultiPinMember:
    complex_bldg_sqft: float | None
    unit_pins: tuple[str, ...]
    year: str
    source: str = SOURCE_ID


@dataclass(frozen=True)
class _Artifact:
    year: str
    by_pin: dict[str, tuple[int, ...]]  # member PIN14 -> indexes into units
    units: tuple[tuple[str, float | None, tuple[str, ...]], ...]


def _undash(pin: str) -> str:
    return pin.replace("-", "").strip()


@lru_cache(maxsize=4)
def _load(path: Path) -> _Artifact:
    try:
        with gzip.open(path, "rt") as fh:
            data = json.load(fh)
        year = str(data["assessor"]["year"])
        units = tuple((str(k), (float(a) if a is not None else None), tuple(pins)) for k, a, pins in data["units"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CapacityArtifactError(f"{path.name} is missing or unreadable: {exc}") from exc
    by_pin: dict[str, list[int]] = {}
    for i, (_, _, pins) in enumerate(units):
        for p in pins:
            by_pin.setdefault(p, []).append(i)
    return _Artifact(year, {p: tuple(ix) for p, ix in by_pin.items()}, units)


def artifact_year(path: Path = ARTIFACT_PATH) -> str:
    """The Assessor year the artifact describes (raises ``CapacityArtifactError`` when it cannot be read)."""
    return _load(path).year


def building_area(pin14: str, path: Path = ARTIFACT_PATH) -> UnitArea | MultiPinMember | None:
    """This PIN's Commercial Valuation building area, or why there is none to attribute (module docstring)."""
    art = _load(path)
    pin = _undash(pin14)
    hits = art.by_pin.get(pin, ())
    if not hits:
        return None
    if len(hits) > 1:
        pins = tuple(sorted({p for i in hits for p in art.units[i][2]}))
        return MultiPinMember(None, pins, art.year)
    _, sqft, pins = art.units[hits[0]]
    if len({p[:10] for p in pins}) > 1:
        return MultiPinMember(sqft, pins, art.year)
    if sqft is None:
        return None
    return UnitArea(sqft, pins, art.year)
