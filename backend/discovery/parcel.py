"""Parcel access behind the evaluator + the dataVersion-keyed snapshot source.

`evaluate(cqs, data_version)` keeps its exact two-argument signature (INV-2
enforcement checklist) by reading the *immutable* parcel snapshot bound to
`data_version` from `default_source` — not a clock, RNG, or mutable global whose
content varies between equal calls. How region/radius membership is resolved is a
backend detail kept behind `Parcel.in_region` (05); the concrete shapely/Socrata
implementation is wired in the API-plumbing step, not here.
"""

from __future__ import annotations

from typing import Any, Iterable, Protocol, runtime_checkable


@runtime_checkable
class Parcel(Protocol):
    """The minimal view the evaluator needs over a parcel."""

    pin: str
    lat: float | None
    lon: float | None

    def get(self, field: str) -> Any:
        """Scalar attribute value, or None when missing (drives `unknownPolicy`)."""
        ...

    def in_region(self, region_ref: str) -> bool:
        """Whether the parcel lies in a region/radius handle (point-in-polygon)."""
        ...


class DictParcel:
    """Dict-backed `Parcel` for fixtures/tests (and a fine default concrete view).

    `regions` is the precomputed set of region handles the parcel belongs to; a real
    concrete view would instead resolve membership geometrically.
    """

    __slots__ = ("pin", "lat", "lon", "_attrs", "_regions")

    def __init__(
        self,
        pin: str,
        attrs: dict[str, Any] | None = None,
        *,
        regions: Iterable[str] | None = None,
        lat: float | None = None,
        lon: float | None = None,
    ) -> None:
        self.pin = pin
        self.lat = lat
        self.lon = lon
        self._attrs = attrs or {}
        self._regions = set(regions or ())

    def get(self, field: str) -> Any:
        return self._attrs.get(field)

    def in_region(self, region_ref: str) -> bool:
        return region_ref in self._regions


class ParcelSource:
    """Content-addressed registry of immutable parcel snapshots keyed by dataVersion.

    A given `data_version` maps to one fixed snapshot — that is what makes
    `evaluate` deterministic per dataVersion (INV-2). In production a data refresh
    ships a new `data_version`; re-registering an existing version replaces it
    (a test convenience; production discipline is to bump the version on change).
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, tuple[Parcel, ...]] = {}

    def register(self, version: str, parcels: Iterable[Parcel]) -> None:
        self._snapshots[version] = tuple(parcels)

    def get(self, version: str) -> tuple[Parcel, ...]:
        if version not in self._snapshots:
            raise KeyError(f"no parcel snapshot registered for dataVersion {version!r}")
        return self._snapshots[version]

    def has(self, version: str) -> bool:
        return version in self._snapshots

    def clear(self) -> None:
        self._snapshots.clear()


# The default snapshot source the evaluator reads from. The real (shapely/Socrata)
# snapshot is registered here at startup in the plumbing step; tests register fixtures.
default_source = ParcelSource()
