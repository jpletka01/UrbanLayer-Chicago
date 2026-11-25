"""Regression tests for topology-safe map geometry transforms."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from shapely import coverage_is_valid
from shapely.geometry import shape
from shapely.ops import unary_union

from backend.map_geometry import (
    simplify_zoning_coverage,
)


FIXTURE = Path(__file__).parent / "fixtures" / "ws3_milwaukee_zoning_adjacent.geojson"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def _geometries(feature_collection: dict):
    return [shape(feature["geometry"]) for feature in feature_collection["features"]]


def test_coverage_simplification_does_not_create_milwaukee_wedge():
    source = _fixture()
    source_geometries = _geometries(source)
    source_union = unary_union(source_geometries)

    # Pin the actual regression: the old independent transform removes a
    # visible wedge from these government polygons.
    independently_simplified = unary_union([
        geometry.simplify(0.0001, preserve_topology=True)
        for geometry in source_geometries
    ])
    assert source_union.difference(independently_simplified).area > 1e-8

    result = simplify_zoning_coverage(source)
    result_geometries = _geometries(result)
    result_union = unary_union(result_geometries)

    assert coverage_is_valid(result_geometries)
    assert source_union.symmetric_difference(result_union).area == pytest.approx(0, abs=1e-18)
    assert [feature["properties"] for feature in result["features"]] == [
        feature["properties"] for feature in source["features"]
    ]


def test_invalid_coverage_falls_back_to_source_geometry():
    overlapping = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"ZONE_CLASS": "RS-3"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"ZONE_CLASS": "B3-2"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]],
                },
            },
        ],
    }

    assert simplify_zoning_coverage(overlapping) is overlapping


