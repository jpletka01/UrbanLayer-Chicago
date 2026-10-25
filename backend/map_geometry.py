"""Geometry transforms for map responses.

Zoning polygons form a coverage: neighboring features are expected to share the
same edge coordinates.  Simplifying each feature independently breaks that
contract and creates visible wedges between districts, so zoning has a dedicated
coverage-aware path instead of using the generic GeoJSON simplifier.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from shapely import coverage_is_valid, coverage_simplify
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, box, mapping, shape
from shapely.ops import polylabel, unary_union


ZONING_SIMPLIFY_TOLERANCE_DEG = 0.00001  # approximately one metre in Chicago
PARCEL_MAP_RADIUS_MI = 0.25


def parcel_map_bounds(
    lat: float,
    lon: float,
    *,
    radius_mi: float = PARCEL_MAP_RADIUS_MI,
) -> tuple[float, float, float, float]:
    """Return the lon/lat envelope used by the parcel-scale zoning query."""
    dlat = radius_mi / 69.0
    dlon = radius_mi / (69.0 * max(math.cos(math.radians(lat)), 0.2))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def _polygonal_part(geometry: Any) -> Polygon | MultiPolygon | None:
    """Keep only positive-area polygonal pieces from an intersection result."""
    if geometry.is_empty:
        return None
    if isinstance(geometry, (Polygon, MultiPolygon)):
        return geometry if geometry.area > 0 else None
    if isinstance(geometry, GeometryCollection):
        polygons: list[Polygon] = []
        for part in geometry.geoms:
            if isinstance(part, Polygon) and part.area > 0:
                polygons.append(part)
            elif isinstance(part, MultiPolygon):
                polygons.extend(p for p in part.geoms if p.area > 0)
        if not polygons:
            return None
        merged = unary_union(polygons)
        return merged if isinstance(merged, (Polygon, MultiPolygon)) else None
    return None


def clip_zoning_coverage(
    feature_collection: dict | None,
    *,
    lat: float,
    lon: float,
    radius_mi: float = PARCEL_MAP_RADIUS_MI,
) -> dict | None:
    """Clip zoning features to the parcel-map envelope without mutating input."""
    if feature_collection is None or "features" not in feature_collection:
        return feature_collection

    envelope = box(*parcel_map_bounds(lat, lon, radius_mi=radius_mi))
    clipped: list[dict] = []
    for feature in feature_collection.get("features", []):
        geometry_data = feature.get("geometry")
        if not geometry_data:
            continue
        try:
            geometry = _polygonal_part(shape(geometry_data).intersection(envelope))
        except Exception:
            # A malformed zoning feature makes the coverage unsafe to transform.
            # Return the original response so callers can still display source data.
            return feature_collection
        if geometry is None:
            continue
        clipped.append({**feature, "geometry": mapping(geometry)})
    return {**feature_collection, "features": clipped}


def _polygon_geometries(features: Iterable[dict]) -> list[Polygon | MultiPolygon] | None:
    geometries: list[Polygon | MultiPolygon] = []
    try:
        for feature in features:
            geometry = shape(feature.get("geometry"))
            if not isinstance(geometry, (Polygon, MultiPolygon)) or geometry.is_empty or not geometry.is_valid:
                return None
            geometries.append(geometry)
    except Exception:
        return None
    return geometries


def simplify_zoning_coverage(
    feature_collection: dict | None,
    *,
    tolerance: float = ZONING_SIMPLIFY_TOLERANCE_DEG,
) -> dict | None:
    """Simplify a valid polygon coverage while preserving all shared edges.

    If the source is not a valid coverage, or the transform cannot be proven to
    preserve its union and feature mapping, return the input unchanged.  Falling
    back to independently simplified polygons would recreate the very gaps this
    helper exists to prevent.
    """
    if feature_collection is None or "features" not in feature_collection:
        return feature_collection
    features = feature_collection.get("features", [])
    if not features:
        return feature_collection

    geometries = _polygon_geometries(features)
    if geometries is None or not coverage_is_valid(geometries):
        return feature_collection

    try:
        # Keep the outer boundary exact. Only shared internal edges need the
        # approximately-one-metre reduction for these viewport-sized payloads.
        simplified = list(coverage_simplify(
            geometries,
            tolerance,
            simplify_boundary=False,
        ))
        if len(simplified) != len(features):
            return feature_collection
        if any(g.is_empty or not g.is_valid for g in simplified):
            return feature_collection
        if not coverage_is_valid(simplified):
            return feature_collection

        before = unary_union(geometries)
        after = unary_union(simplified)
        # With the outer boundary held fixed, any area delta means the coverage
        # transform did not preserve what the source said. Allow only floating-
        # point dust relative to the coverage area.
        epsilon = max(before.area * 1e-10, 1e-18)
        if before.symmetric_difference(after).area > epsilon:
            return feature_collection
    except Exception:
        return feature_collection

    return {
        **feature_collection,
        "features": [
            {**feature, "geometry": mapping(geometry)}
            for feature, geometry in zip(features, simplified)
        ],
    }


def prepare_parcel_zoning(
    feature_collection: dict | None,
    *,
    lat: float,
    lon: float,
    radius_mi: float = PARCEL_MAP_RADIUS_MI,
) -> dict | None:
    """Clip and safely simplify a parcel-scale zoning coverage."""
    clipped = clip_zoning_coverage(
        feature_collection,
        lat=lat,
        lon=lon,
        radius_mi=radius_mi,
    )
    return simplify_zoning_coverage(clipped)


def _polygon_parts(geometry: Polygon | MultiPolygon) -> Iterable[Polygon]:
    if isinstance(geometry, Polygon):
        yield geometry
    else:
        yield from geometry.geoms


def zoning_label_points(feature_collection: dict | None) -> list[dict]:
    """Return one interior label anchor for each exact zoning class.

    The largest visible polygon wins when a class occurs in several fragments.
    ``polylabel`` gives an interior visual centre for concave shapes; the
    guaranteed-interior representative point is the defensive fallback.
    """
    if feature_collection is None:
        return []

    largest_by_class: dict[str, Polygon] = {}
    for feature in feature_collection.get("features", []):
        zone_class = str((feature.get("properties") or {}).get("ZONE_CLASS") or "").strip()
        if not zone_class or not feature.get("geometry"):
            continue
        try:
            geometry = shape(feature["geometry"])
        except Exception:
            continue
        if not isinstance(geometry, (Polygon, MultiPolygon)):
            continue
        for polygon in _polygon_parts(geometry):
            current = largest_by_class.get(zone_class)
            if not polygon.is_empty and polygon.area > 0 and (current is None or polygon.area > current.area):
                largest_by_class[zone_class] = polygon

    labels: list[dict] = []
    for zone_class, polygon in largest_by_class.items():
        try:
            point = polylabel(polygon, tolerance=0.000001)
        except Exception:
            point = polygon.representative_point()
        if not polygon.covers(point):
            point = polygon.representative_point()
        labels.append({
            "zone_class": zone_class,
            "position": [point.x, point.y],
        })
    return labels
