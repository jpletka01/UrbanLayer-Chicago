"""Shared reader for HUD's tract-designation layers (Opportunity Zones, QCTs, NMTC).

ArcGIS answers a failed query with HTTP 200 and an ``{"error": {...}}`` body. Read as "no
features", that cached "not designated" for 24 hours (decision Item 65). A body without a feature
list raises here, so only a real empty result means "this tract is not in the layer".
"""

from __future__ import annotations


class HudLayerError(RuntimeError):
    """A HUD tract layer didn't answer: "not checked", never "not designated"."""


def tract_features(data: object, layer: str) -> list[dict]:
    """The ``features`` of a HUD ArcGIS query response, or raise ``HudLayerError``."""
    if not isinstance(data, dict):
        raise HudLayerError(f"{layer}: response is not a JSON object")
    if data.get("error"):
        raise HudLayerError(f"{layer}: ArcGIS error {data['error']!r}")
    features = data.get("features")
    if not isinstance(features, list):
        raise HudLayerError(f"{layer}: response has no feature list")
    return features
