"""Regression tests for Report V6 Tier-2 D3 — map scale bar + radius ring.

The three always-rendering report maps (zoning/cover, construction, comps) already
carried styled legends; D3's remaining gap was a **scale bar** and a **distance
reference ring**, both derived from the basemap's actual Web Mercator projection so
they can't misstate distance.

Covers:
  * `_rendered_m_per_px` — metres-per-pixel matches Web Mercator with the `@2x`
    retina factor baked into `_latlon_to_px` (the `* 2`).
  * `_draw_scale_and_ring` — adds a ring (Circle) + a scale bar to an Axes, and
    picks a sensible round scale-bar distance.
  * End-to-end smoke — each map generator still returns a PNG (non-None base64)
    with the overlays drawn, on a synthetic basemap (GIS-independent).

See claude-context/guides/report-v6-execution-plan.md ("Phase 4 — RE-PRIORITIZED", D3).
"""

import base64
import io
from math import cos, radians

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest
from PIL import Image

from backend.report_builder import (
    _draw_scale_and_ring,
    _generate_comps_map,
    _generate_construction_map,
    _generate_zoning_map,
    _rendered_m_per_px,
)
from backend.models import ComparableSale

# Subject coordinates near the QA parcels (Lincoln Park).
LAT, LON = 41.9270, -87.6500
# Maps are fetched @2x, so the rendered PNG is 1200x800 (2x the requested 600x400).
IMG_W, IMG_H = 1200, 800


def _synthetic_basemap() -> bytes:
    """A solid 1200x800 PNG standing in for the Mapbox @2x basemap."""
    buf = io.BytesIO()
    Image.new("RGB", (IMG_W, IMG_H), (20, 20, 20)).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# _rendered_m_per_px
# ---------------------------------------------------------------------------

def test_rendered_m_per_px_matches_web_mercator_with_retina_factor():
    """At zoom 15 / lat ~41.9 the rendered resolution is ~1.78 m/px (256-tile / 2)."""
    val = _rendered_m_per_px(LAT, 15)
    expected = 156543.03392804097 * cos(radians(LAT)) / (2 ** 15) / 2
    assert val == pytest.approx(expected)
    assert val == pytest.approx(1.78, abs=0.05)


def test_rendered_m_per_px_halves_each_zoom_step():
    """One zoom level in covers half the ground per pixel."""
    z14 = _rendered_m_per_px(LAT, 14)
    z15 = _rendered_m_per_px(LAT, 15)
    assert z15 == pytest.approx(z14 / 2, rel=1e-9)


def test_rendered_m_per_px_shrinks_with_latitude():
    """cos(lat) factor: higher latitude => fewer metres per pixel."""
    assert _rendered_m_per_px(60.0, 15) < _rendered_m_per_px(10.0, 15)


# ---------------------------------------------------------------------------
# _draw_scale_and_ring
# ---------------------------------------------------------------------------

def _fresh_axes():
    fig, ax = plt.subplots()
    ax.set_xlim(0, IMG_W)
    ax.set_ylim(IMG_H, 0)  # inverted, as the maps do
    return fig, ax


def test_draw_scale_and_ring_adds_ring_and_scalebar():
    fig, ax = _fresh_axes()
    patches_before = len(ax.patches)
    lines_before = len(ax.lines)

    _draw_scale_and_ring(ax, LAT, 15, IMG_W, IMG_H, ring_mi=0.25)

    # one Circle patch for the ring
    from matplotlib.patches import Circle
    rings = [p for p in ax.patches if isinstance(p, Circle)]
    assert len(rings) == 1
    assert len(ax.patches) == patches_before + 1
    # ring is centred on the subject pin (image centre) with a positive radius
    cx, cy = rings[0].center
    assert cx == pytest.approx(IMG_W / 2)
    assert cy == pytest.approx(IMG_H / 2)
    assert rings[0].radius > 0
    # scale bar adds line segments (bar + two end ticks)
    assert len(ax.lines) >= lines_before + 3
    plt.close(fig)


def test_draw_scale_and_ring_without_ring_still_draws_scalebar():
    fig, ax = _fresh_axes()
    _draw_scale_and_ring(ax, LAT, 15, IMG_W, IMG_H, ring_mi=None)
    from matplotlib.patches import Circle
    assert not [p for p in ax.patches if isinstance(p, Circle)]
    assert len(ax.lines) >= 3  # scale bar still present
    plt.close(fig)


def test_draw_scale_and_ring_picks_round_scalebar_distance():
    """The scale-bar label is one of the predefined round distances."""
    fig, ax = _fresh_axes()
    _draw_scale_and_ring(ax, LAT, 15, IMG_W, IMG_H, ring_mi=0.25)
    labels = {t.get_text() for t in ax.texts}
    assert any(lbl in labels for lbl in ("0.05 mi", "0.1 mi", "0.25 mi", "0.5 mi", "1 mi", "2 mi"))
    plt.close(fig)


def test_draw_scale_and_ring_never_raises_on_bad_input():
    """Best-effort: a degenerate latitude must not bubble an exception."""
    fig, ax = _fresh_axes()
    _draw_scale_and_ring(ax, 90.0, 15, IMG_W, IMG_H, ring_mi=0.25)  # cos(90)=0
    plt.close(fig)


# ---------------------------------------------------------------------------
# End-to-end smoke: the three maps still render with the overlays.
# ---------------------------------------------------------------------------

def _is_png_b64(s) -> bool:
    if not isinstance(s, str):
        return False
    return base64.b64decode(s)[:8] == b"\x89PNG\r\n\x1a\n"


def test_zoning_map_renders_with_overlays():
    geojson = {
        "features": [{
            "properties": {"ZONE_CLASS": "RM5"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [LON - 0.001, LAT - 0.001], [LON + 0.001, LAT - 0.001],
                    [LON + 0.001, LAT + 0.001], [LON - 0.001, LAT + 0.001],
                    [LON - 0.001, LAT - 0.001],
                ]],
            },
        }]
    }
    out = _generate_zoning_map(LAT, LON, geojson, _synthetic_basemap())
    assert _is_png_b64(out)


def test_construction_map_renders_with_overlays():
    projects = [
        {"latitude": str(LAT + 0.001), "longitude": str(LON + 0.001),
         "permit_type": "PERMIT - NEW CONSTRUCTION"},
        {"latitude": str(LAT - 0.001), "longitude": str(LON - 0.001),
         "permit_type": "PERMIT - WRECKING/DEMOLITION"},
    ]
    out = _generate_construction_map(LAT, LON, projects, _synthetic_basemap())
    assert _is_png_b64(out)


def test_comps_map_renders_with_overlays():
    sales = [
        ComparableSale(pin="1", lat=LAT + 0.0008, lon=LON + 0.0008, sale_price=300000),
        ComparableSale(pin="2", lat=LAT - 0.0008, lon=LON - 0.0008, sale_price=350000),
    ]
    out = _generate_comps_map(LAT, LON, sales, _synthetic_basemap())
    assert _is_png_b64(out)
