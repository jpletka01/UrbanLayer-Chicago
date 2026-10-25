"""Regression tests for topology-safe map geometry transforms."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from shapely import coverage_is_valid
from shapely.geometry import Point, shape
from shapely.ops import unary_union

from backend.map_geometry import (
    prepare_parcel_zoning,
    simplify_zoning_coverage,
    zoning_label_points,
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


def test_prepare_parcel_zoning_clips_to_requested_envelope():
    source = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"ZONE_CLASS": "RS-3"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-88, 41], [-87, 41], [-87, 42], [-88, 42], [-88, 41]]],
            },
        }],
    }

    result = prepare_parcel_zoning(source, lat=41.91, lon=-87.68, radius_mi=0.25)
    min_x, min_y, max_x, max_y = shape(result["features"][0]["geometry"]).bounds

    assert -87.69 < min_x < -87.68
    assert -87.68 < max_x < -87.67
    assert 41.90 < min_y < 41.91
    assert 41.91 < max_y < 41.92


def test_label_points_are_inside_largest_polygon_for_each_exact_class():
    source = _fixture()
    labels = zoning_label_points(source)

    assert [label["zone_class"] for label in labels] == ["RT-4", "RS-3"]
    assert len(labels) == 2
    for label in labels:
        polygons = [
            shape(feature["geometry"])
            for feature in source["features"]
            if feature["properties"]["ZONE_CLASS"] == label["zone_class"]
        ]
        assert unary_union(polygons).covers(Point(label["position"]))
