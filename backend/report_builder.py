"""$25 Development Feasibility Report — data assembly + deterministic synthesis.

Extracted verbatim from backend/main.py (2026-07-09, mechanical move — no logic
changes; git history of main.py has the full evolution). Everything here is the
report *builder*: parcel/zoning/comps data assembly (`_fetch_report_data`),
matplotlib map + chart rasters (zoning quilt, construction, comps, parcel outline,
development envelope), and the deterministic narrative/scoring passes
(opportunities/constraints, land-value range, decision box, approval pathway —
no LLM calls anywhere). The HTTP route, Jinja HTML render, and the isolated
WeasyPrint child (`report_render.py`) stay in main.py; localization lives in
`report_i18n.py`. `_comp_class_prefix` is shared with the scorecard path.

Remaining coupling: `_fetch_report_data` reuses main's `_fetch_scorecard_data`
(shared parcel aggregation) and `_limited` (the process-wide retrieval
semaphore) via a lazy import at call time — main is fully loaded before any
request runs, so there is no import cycle. If a future pass wants to cut that
seam, those two belong in a shared module, not a second copy here (a second
semaphore would double the retrieval concurrency cap).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from backend import report_i18n
from backend.config import get_settings
from backend.models import (
    ComparableSale,
    ComparablesSummary,
    ReportData,
    ZoningStandards,
)
from backend.retrieval.property.assessment_level import assessment_level_for_class
from backend.retrieval.utils import FT_PER_DEG_LAT, MI_PER_DEG_LAT
from backend.retrieval.vector_search import semantic_search
from backend.retrieval.zoning import adjacent_parcel_zoning

log = logging.getLogger(__name__)

_ZONE_PREFIX_COLORS: dict[str, tuple[int, int, int]] = {
    "RS": (255, 235, 59),
    "RT": (255, 224, 130),
    "RM": (255, 213, 79),
    "B": (66, 133, 244),
    "C": (156, 39, 176),
    "M": (233, 30, 99),
    "PD": (158, 158, 158),
    "PMD": (176, 176, 176),
    "D": (0, 150, 136),
    "DC": (0, 150, 136),
    "DX": (38, 166, 154),
    "DR": (77, 182, 172),
    "DS": (0, 137, 123),
    "T": (141, 110, 99),
    "P": (76, 175, 80),
    "POS": (102, 187, 106),
}
_ZONE_FALLBACK = (120, 120, 120)

_ZONE_LABELS: dict[str, str] = {
    "RS": "Residential Single",
    "RT": "Residential Two-Flat",
    "RM": "Residential Multi",
    "B": "Business",
    "C": "Commercial",
    "M": "Manufacturing",
    "PD": "Planned Dev",
    "PMD": "Planned Mfg",
    "D": "Downtown",
    "DC": "Downtown Core",
    "DX": "Downtown Mixed",
    "DR": "Downtown Res",
    "DS": "Downtown Svc",
    "T": "Transportation",
    "P": "Parks",
    "POS": "Open Space",
}


def _zone_prefix(zone_class: str) -> str:
    import re
    m = re.match(r"^([A-Z]+)", (zone_class or "").strip().upper())
    return m.group(1) if m else ""


def _latlon_to_px(
    lat: float, lon: float,
    lat0: float, lon0: float,
    zoom: int, w: int, h: int,
) -> tuple[float, float]:
    from math import log, tan, radians, cos, pi
    scale = 256 * (2 ** zoom)
    x = (lon + 180) / 360 * scale
    y = (1 - log(tan(radians(lat)) + 1 / cos(radians(lat))) / pi) / 2 * scale
    cx = (lon0 + 180) / 360 * scale
    cy = (1 - log(tan(radians(lat0)) + 1 / cos(radians(lat0))) / pi) / 2 * scale
    return (x - cx + w / 2) * 2, (y - cy + h / 2) * 2


def _rendered_m_per_px(lat: float, zoom: int) -> float:
    """Ground metres per rendered pixel for the report basemaps at a given zoom.

    Web Mercator ground resolution is ``156543.03 * cos(lat) / 2**zoom`` metres per
    pixel for a 256-px tile. ``_latlon_to_px`` scales its output by ``* 2`` (the maps
    are fetched as Mapbox ``@2x`` retina images, so the actual PNG is 2× the requested
    600×400), which halves the metres each pixel covers — hence the extra ``/ 2``.
    Keeping this in one place ensures the scale bar and radius ring match the exact
    projection used to place every marker.
    """
    from math import cos, radians

    return 156543.03392804097 * cos(radians(lat)) / (2 ** zoom) / 2


_SCALE_BAR_MILES = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0)


def _draw_scale_and_ring(
    ax,
    lat: float,
    zoom: int,
    img_w: int,
    img_h: int,
    ring_mi: float | None,
) -> None:
    """Overlay a scale bar (bottom-left) and a distance reference ring on a report map.

    Both are orientation aids drawn in the same pixel space markers use. ``ring_mi`` is
    a *distance reference* around the subject pin (not a claimed data boundary), so it
    stays truthful even when, e.g., the comps search widens past it. Best-effort: any
    failure is swallowed so a map still renders without these overlays.
    """
    from matplotlib.patches import Circle

    MI_M = 1609.344
    try:
        m_per_px = _rendered_m_per_px(lat, zoom)
        if m_per_px <= 0:
            return
        cx, cy = img_w / 2, img_h / 2

        # --- distance reference ring around the subject pin ---
        if ring_mi:
            r_px = ring_mi * MI_M / m_per_px
            # only draw if it comfortably fits inside the frame
            if 0 < r_px < min(img_w, img_h) / 2:
                ax.add_patch(Circle(
                    (cx, cy), r_px, fill=False,
                    edgecolor="#ffffff", linewidth=0.8,
                    linestyle=(0, (4, 3)), alpha=0.55, zorder=9,
                ))
                ax.text(
                    cx, cy - r_px - 3, f"{ring_mi:g} mi",
                    ha="center", va="bottom", fontsize=4.5,
                    color="#ffffff", alpha=0.85,
                    bbox=dict(facecolor="#0d0d0d", alpha=0.6, edgecolor="none", pad=1.5),
                    zorder=15,
                )

        # --- scale bar (bottom-left): largest round distance under ~¼ of the width ---
        target_m = (img_w / 4) * m_per_px
        bar_mi = _SCALE_BAR_MILES[0]
        for cand in _SCALE_BAR_MILES:
            if cand * MI_M <= target_m:
                bar_mi = cand
        bar_px = bar_mi * MI_M / m_per_px
        x0, y0 = 14.0, img_h - 16.0
        ax.plot([x0, x0 + bar_px], [y0, y0], color="#ffffff",
                linewidth=1.6, alpha=0.9, solid_capstyle="butt", zorder=16)
        for xt in (x0, x0 + bar_px):
            ax.plot([xt, xt], [y0 - 3, y0 + 3], color="#ffffff",
                    linewidth=1.2, alpha=0.9, zorder=16)
        ax.text(
            x0 + bar_px / 2, y0 - 5, f"{bar_mi:g} mi",
            ha="center", va="bottom", fontsize=4.5,
            color="#ffffff", alpha=0.9,
            bbox=dict(facecolor="#0d0d0d", alpha=0.6, edgecolor="none", pad=1.5),
            zorder=16,
        )
    except Exception:
        log.warning("Failed to draw scale bar / radius ring", exc_info=True)


def _generate_zoning_map(
    lat: float,
    lon: float,
    zoning_geojson: dict,
    basemap_bytes: bytes,
    overlay_geojson: dict | None = None,
) -> str | None:
    """Generate a base64-encoded PNG map with zoning polygon overlays and regulatory boundaries."""
    import base64
    import io

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MplPolygon
        from PIL import Image
    except ImportError:
        log.warning("matplotlib/Pillow not available, skipping zoning map")
        return None

    MAP_W, MAP_H, ZOOM = 600, 400, 15

    try:
        basemap = Image.open(io.BytesIO(basemap_bytes))
        img_w, img_h = basemap.size

        dpi = 150
        fig, ax = plt.subplots(
            figsize=(img_w / dpi, img_h / dpi), dpi=dpi,
        )
        ax.imshow(basemap, extent=[0, img_w, img_h, 0], aspect="auto")
        ax.set_xlim(0, img_w)
        ax.set_ylim(img_h, 0)
        ax.axis("off")

        seen_prefixes: dict[str, tuple[float, float, float]] = {}

        features = zoning_geojson.get("features") or []
        for feat in features:
            props = feat.get("properties") or {}
            zone_class = props.get("ZONE_CLASS", "")
            prefix = _zone_prefix(zone_class)
            rgb = _ZONE_PREFIX_COLORS.get(prefix, _ZONE_FALLBACK)
            fc = (rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)

            if prefix and prefix not in seen_prefixes:
                seen_prefixes[prefix] = fc

            geom = feat.get("geometry") or {}
            geom_type = geom.get("type", "")
            coord_rings: list[list] = []

            if geom_type == "Polygon":
                coord_rings = geom.get("coordinates") or []
            elif geom_type == "MultiPolygon":
                for poly in geom.get("coordinates") or []:
                    coord_rings.extend(poly)

            for ring in coord_rings:
                pixels = []
                in_view = False
                for coord in ring:
                    px, py = _latlon_to_px(
                        coord[1], coord[0], lat, lon, ZOOM, MAP_W, MAP_H,
                    )
                    pixels.append((px, py))
                    if 0 <= px <= img_w and 0 <= py <= img_h:
                        in_view = True

                if not in_view or len(pixels) < 3:
                    continue

                patch = MplPolygon(
                    pixels, closed=True,
                    facecolor=(*fc, 0.35),
                    edgecolor=(*fc, 0.7),
                    linewidth=0.5,
                )
                ax.add_patch(patch)

        # Draw regulatory overlay boundaries (dashed outlines)
        _OVERLAY_COLORS = {
            "landmark_district": ("#f59e0b", "Landmark"),
            "historic_district": ("#f59e0b", "Historic"),
            "national_register": ("#fbbf24", "Nat'l Register"),
            "planned_development": ("#8b5cf6", "Planned Dev"),
            "ssa": ("#06b6d4", "SSA"),
            "pedestrian_street": ("#ec4899", "Ped. Street"),
        }
        overlay_legend: list[tuple[str, str, str]] = []
        if overlay_geojson:
            for feat in (overlay_geojson.get("features") or []):
                props = feat.get("properties") or {}
                otype = props.get("overlay_type", "")
                if otype not in _OVERLAY_COLORS:
                    continue
                color_hex, label = _OVERLAY_COLORS[otype]
                oname = props.get("NAME") or props.get("DIST_NAME") or label
                if (color_hex, oname) not in [(c, n) for c, _, n in overlay_legend]:
                    overlay_legend.append((color_hex, label, oname))

                geom = feat.get("geometry") or {}
                geom_type = geom.get("type", "")
                coord_rings: list[list] = []
                if geom_type == "Polygon":
                    coord_rings = geom.get("coordinates") or []
                elif geom_type == "MultiPolygon":
                    for poly in geom.get("coordinates") or []:
                        coord_rings.extend(poly)

                for ring in coord_rings:
                    pixels = []
                    for coord in ring:
                        px, py = _latlon_to_px(coord[1], coord[0], lat, lon, ZOOM, MAP_W, MAP_H)
                        pixels.append((px, py))
                    if len(pixels) < 3:
                        continue
                    patch = MplPolygon(
                        pixels, closed=True,
                        facecolor="none",
                        edgecolor=color_hex,
                        linewidth=1.5,
                        linestyle="--",
                        zorder=8,
                    )
                    ax.add_patch(patch)

        pin_px, pin_py = img_w / 2, img_h / 2
        ax.plot(
            pin_px, pin_py, "o",
            markersize=10, color="#c96442",
            markeredgecolor="white", markeredgewidth=2,
            zorder=10,
        )

        if seen_prefixes:
            sorted_prefixes = sorted(
                seen_prefixes.items(),
                key=lambda kv: list(_ZONE_PREFIX_COLORS.keys()).index(kv[0])
                if kv[0] in _ZONE_PREFIX_COLORS else 99,
            )
            legend_handles = []
            for prefix, color in sorted_prefixes:
                label = _ZONE_LABELS.get(prefix, prefix)
                handle = plt.Line2D(
                    [0], [0], marker="s", color="none",
                    markerfacecolor=(*color, 0.6),
                    markeredgecolor=(*color, 0.9),
                    markersize=6, label=label,
                )
                legend_handles.append(handle)

            for color_hex, label, oname in overlay_legend:
                handle = plt.Line2D(
                    [0], [0], color=color_hex,
                    linewidth=1.5, linestyle="--",
                    label=oname[:20],
                )
                legend_handles.append(handle)

            legend = ax.legend(
                handles=legend_handles,
                loc="upper right",
                fontsize=5.5,
                frameon=True,
                framealpha=0.8,
                facecolor="#1a1a1a",
                edgecolor="#333333",
                labelcolor="white",
                handletextpad=0.4,
                borderpad=0.4,
                borderaxespad=0.6,
            )
            legend.set_zorder(20)

        ax.text(
            img_w / 2, img_h - 8,
            "Sources: City of Chicago Zoning Map (ArcGIS) · Mapbox · OpenStreetMap",
            ha="center", va="bottom",
            fontsize=4.5, color="#999999",
            bbox=dict(
                facecolor="#0d0d0d", alpha=0.7,
                edgecolor="none", pad=3,
            ),
            zorder=15,
        )

        _draw_scale_and_ring(ax, lat, ZOOM, img_w, img_h, ring_mi=0.25)

        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        buf = io.BytesIO()
        fig.savefig(
            buf, format="png", bbox_inches="tight",
            pad_inches=0, facecolor="#0d0d0d",
        )
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("ascii")

    except Exception:
        log.warning("Failed to generate zoning map", exc_info=True)
        return None


def _generate_construction_map(
    lat: float,
    lon: float,
    projects: list[dict],
    basemap_bytes: bytes,
) -> str | None:
    """Generate a base64-encoded PNG map with construction/demolition markers."""
    import base64
    import io

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from PIL import Image
    except ImportError:
        return None

    MAP_W, MAP_H, ZOOM = 600, 400, 14

    try:
        basemap = Image.open(io.BytesIO(basemap_bytes))
        img_w, img_h = basemap.size

        dpi = 150
        fig, ax = plt.subplots(figsize=(img_w / dpi, img_h / dpi), dpi=dpi)
        ax.imshow(basemap, extent=[0, img_w, img_h, 0], aspect="auto")
        ax.set_xlim(0, img_w)
        ax.set_ylim(img_h, 0)
        ax.axis("off")

        has_construction = False
        has_demolition = False

        for idx, proj in enumerate(projects[:10], start=1):
            try:
                plat = float(proj.get("latitude", 0))
                plon = float(proj.get("longitude", 0))
            except (ValueError, TypeError):
                continue
            if plat == 0 or plon == 0:
                continue

            px, py = _latlon_to_px(plat, plon, lat, lon, ZOOM, MAP_W, MAP_H)
            if not (0 <= px <= img_w and 0 <= py <= img_h):
                continue

            ptype = proj.get("permit_type", "")
            is_demo = "WRECKING" in ptype or "DEMOLITION" in ptype
            if is_demo:
                color = "#ef4444"
                marker = "s"
                has_demolition = True
            else:
                color = "#10b981"
                marker = "o"
                has_construction = True
            ax.plot(px, py, marker, markersize=10, color=color,
                    markeredgecolor="white", markeredgewidth=1.2, zorder=5)
            ax.text(px, py, str(idx), ha="center", va="center",
                    fontsize=5.5, fontweight="bold", color="white", zorder=6)

        # Subject property pin
        pin_px, pin_py = img_w / 2, img_h / 2
        ax.plot(pin_px, pin_py, "D", markersize=9, color="#2563eb",
                markeredgecolor="white", markeredgewidth=2, zorder=10)

        legend_handles = []
        if has_construction:
            legend_handles.append(plt.Line2D(
                [0], [0], marker="o", color="none", markerfacecolor="#10b981",
                markeredgecolor="white", markersize=6, label="New Construction",
            ))
        if has_demolition:
            legend_handles.append(plt.Line2D(
                [0], [0], marker="s", color="none", markerfacecolor="#ef4444",
                markeredgecolor="white", markersize=6, label="Demolition",
            ))
        legend_handles.append(plt.Line2D(
            [0], [0], marker="D", color="none", markerfacecolor="#2563eb",
            markeredgecolor="white", markersize=6, label="Subject Property",
        ))

        legend = ax.legend(
            handles=legend_handles, loc="upper right", fontsize=5.5,
            frameon=True, framealpha=0.8, facecolor="#1a1a1a",
            edgecolor="#333333", labelcolor="white",
            handletextpad=0.4, borderpad=0.4, borderaxespad=0.6,
        )
        legend.set_zorder(20)

        ax.text(
            img_w / 2, img_h - 8,
            "Sources: City of Chicago Building Permits · Mapbox · OpenStreetMap",
            ha="center", va="bottom", fontsize=4.5, color="#999999",
            bbox=dict(facecolor="#0d0d0d", alpha=0.7, edgecolor="none", pad=3),
            zorder=15,
        )

        # 0.5 mi ring matches the nearby-construction search radius (config 0.00725 deg)
        _draw_scale_and_ring(ax, lat, ZOOM, img_w, img_h, ring_mi=0.5)

        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight",
                    pad_inches=0, facecolor="#0d0d0d")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("ascii")

    except Exception:
        log.warning("Failed to generate construction map", exc_info=True)
        return None


def _generate_comps_map(
    lat: float,
    lon: float,
    sales: list["ComparableSale"],
    basemap_bytes: bytes,
) -> str | None:
    """Generate a base64-encoded PNG map with comparable sale locations."""
    import base64
    import io

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from PIL import Image
    except ImportError:
        return None

    MAP_W, MAP_H, ZOOM = 600, 400, 15

    try:
        basemap = Image.open(io.BytesIO(basemap_bytes))
        img_w, img_h = basemap.size

        dpi = 150
        fig, ax = plt.subplots(figsize=(img_w / dpi, img_h / dpi), dpi=dpi)
        ax.imshow(basemap, extent=[0, img_w, img_h, 0], aspect="auto")
        ax.set_xlim(0, img_w)
        ax.set_ylim(img_h, 0)
        ax.axis("off")

        for i, sale in enumerate(sales[:15]):
            slat = getattr(sale, "lat", None) or (sale.get("lat") if isinstance(sale, dict) else None)
            slon = getattr(sale, "lon", None) or (sale.get("lon") if isinstance(sale, dict) else None)
            if not slat or not slon:
                continue
            px, py = _latlon_to_px(slat, slon, lat, lon, ZOOM, MAP_W, MAP_H)
            if not (0 <= px <= img_w and 0 <= py <= img_h):
                continue
            ax.plot(
                px, py, "D",
                markersize=7, color="#22d3ee",
                markeredgecolor="white", markeredgewidth=0.8,
                zorder=5,
            )
            ax.annotate(
                str(i + 1),
                (px, py), color="white", fontsize=4.5,
                fontweight="bold", ha="center", va="center",
                zorder=6,
            )

        # Subject property
        pin_px, pin_py = img_w / 2, img_h / 2
        ax.plot(
            pin_px, pin_py, "o",
            markersize=10, color="#c96442",
            markeredgecolor="white", markeredgewidth=2,
            zorder=10,
        )

        legend_handles = [
            plt.Line2D([0], [0], marker="D", color="none", markerfacecolor="#22d3ee",
                       markeredgecolor="white", markersize=6, label="Comparable Sale"),
            plt.Line2D([0], [0], marker="o", color="none", markerfacecolor="#c96442",
                       markeredgecolor="white", markersize=6, label="Subject Property"),
        ]
        legend = ax.legend(
            handles=legend_handles, loc="upper right",
            fontsize=5.5, frameon=True, framealpha=0.8,
            facecolor="#1a1a1a", edgecolor="#333333", labelcolor="white",
            handletextpad=0.4, borderpad=0.4, borderaxespad=0.6,
        )
        legend.set_zorder(20)

        # 0.25 mi distance reference (comps search starts at ~0.28 mi and may widen)
        _draw_scale_and_ring(ax, lat, ZOOM, img_w, img_h, ring_mi=0.25)

        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0, facecolor="#0d0d0d")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("ascii")

    except Exception:
        log.warning("Failed to generate comps map", exc_info=True)
        return None


def _generate_comps_chart(comps: "ComparablesSummary") -> str | None:
    """Generate a base64-encoded PNG scatter chart of comparable sales."""
    import base64
    import io
    from datetime import datetime

    if not comps or not comps.sales or len(comps.sales) < 2:
        return None

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        log.warning("matplotlib not available, skipping comps chart")
        return None

    dates = []
    prices = []
    for s in comps.sales:
        if s.sale_date and s.sale_price:
            try:
                dt = datetime.strptime(s.sale_date[:10], "%Y-%m-%d")
                dates.append(dt)
                prices.append(s.sale_price)
            except ValueError:
                continue

    if len(dates) < 2:
        return None

    fig, ax = plt.subplots(figsize=(5.5, 2.5), dpi=150)
    ax.scatter(
        dates, [p / 1000 for p in prices],
        c="#2563eb", s=50, zorder=3, edgecolors="white", linewidth=0.5,
    )

    if comps.median_sale_price:
        ax.axhline(
            y=comps.median_sale_price / 1000,
            color="#9ca3af", linestyle="--", linewidth=0.8,
            label=f"Median ${comps.median_sale_price:,.0f}",
        )
        ax.legend(fontsize=7, loc="upper left", frameon=False)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.set_ylabel("Sale Price ($K)", fontsize=8, color="#374151")
    ax.set_xlabel("", fontsize=8)
    ax.tick_params(axis="both", labelsize=7, colors="#6b7280")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#e5e7eb")
    ax.spines["bottom"].set_color("#e5e7eb")
    ax.grid(axis="y", color="#f3f4f6", linewidth=0.5)
    ax.set_axisbelow(True)

    fig.tight_layout(pad=0.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _comp_class_prefix(bldg_class: str | None, zone_class: str | None) -> str:
    """Choose the Cook County class prefix for comparable-sales search.

    Marketable subjects use their own class family (first digit). Non-marketable
    subjects (exempt class "EX", or non-numeric/unknown classes that never trade)
    fall back to a class implied by zoning, so a redevelopment reader still gets
    comps. Cook County: 2xx residential, 5xx commercial/industrial.
    """
    bc = (bldg_class or "").strip().upper()
    if bc and bc[0].isdigit() and not bc.startswith("EX"):
        return bc[0]

    z = (zone_class or "").strip().upper()
    if z.startswith(("RS", "RT", "RM", "DR")):
        return "2"
    if z.startswith(("B", "C", "M", "DX", "DC", "DS", "PMD")):
        return "5"
    return "2"  # default to residential comps


async def _fetch_report_data(
    resolved_lat: float,
    resolved_lon: float,
    resolved_address: str | None,
    *,
    pin: str | None = None,
    confidence: str | None = None,
    language: str = "en",
) -> "ReportData":
    """Fetch all data for a v2 development feasibility report.

    ``pin``/``confidence`` come from _resolve_location: ``pin`` keys the property
    domain by parcel identity; ``confidence`` drives the INV-5 disclosure on the
    artifact when resolution was degraded ("approximate").
    """
    from backend.models import (
        ComparablesSummary, ComparableSale, NearbyDevelopment, ReportData,
    )
    from backend.retrieval.buildings import (
        address_specific_permits, address_specific_violations,
        nearby_new_construction, parse_chicago_address,
    )
    from backend.retrieval.property.sales import nearby_comparable_sales
    from backend.zoning_extract import calculate_development_potential
    from backend.zoning_cache import get_cached_zoning_standards
    # Shared with main/scorecard: the parcel aggregation + the process-wide
    # retrieval semaphore (a local copy would double the concurrency cap).
    # Lazy on purpose — main imports this module, so a top-level import back
    # into main would be circular; by request time main is fully loaded.
    from backend.main import _fetch_scorecard_data, _limited

    settings = get_settings()

    # Step 1: Base scorecard data
    base = await _fetch_scorecard_data(resolved_lat, resolved_lon, resolved_address, pin=pin)
    ctx = base["context"]
    partial_failures: list[str] = list(base.get("partial_failures", []))

    # Step 2: v2 data retrievals in parallel
    zone_class = ctx.parcel_zoning.zone_class if ctx.parcel_zoning else None
    v2_tasks: dict[str, asyncio.Task] = {}

    v2_tasks["adjacent_zoning"] = asyncio.create_task(
        _limited(adjacent_parcel_zoning(resolved_lat, resolved_lon))
    )

    if resolved_address:
        parsed = parse_chicago_address(resolved_address)
        if parsed:
            v2_tasks["address_permits"] = asyncio.create_task(
                _limited(address_specific_permits(
                    parsed["number"], parsed["direction"], parsed["name"]
                ))
            )
            v2_tasks["address_violations"] = asyncio.create_task(
                _limited(address_specific_violations(
                    parsed["number"], parsed["direction"], parsed["name"]
                ))
            )

    # Comparable sales. For marketable parcels use the subject's own class family;
    # for non-marketable subjects (exempt / unknown class) derive the comp class
    # from zoning so a redevelopment reader still gets a valuation basis.
    class_prefix = _comp_class_prefix(
        ctx.property.bldg_class if ctx.property else None, zone_class
    )
    if class_prefix:
        v2_tasks["comparable_sales"] = asyncio.create_task(
            _limited(nearby_comparable_sales(resolved_lat, resolved_lon, class_prefix))
        )

    v2_tasks["nearby_construction"] = asyncio.create_task(
        _limited(nearby_new_construction(resolved_lat, resolved_lon, radius_deg=settings.nearby_construction_radius_deg))
    )

    # Gather v2 results
    v2_done = await asyncio.gather(*v2_tasks.values(), return_exceptions=True)
    v2_results: dict[str, Any] = {}
    _V2_FAILURE_MAP = {
        "adjacent_zoning": "adjacent zoning",
        "address_permits": "address-specific permits",
        "address_violations": "address-specific violations",
        "comparable_sales": "comparable sales",
        "nearby_construction": "nearby construction activity",
    }
    for key, value in zip(v2_tasks.keys(), v2_done):
        if isinstance(value, Exception):
            log.warning("Report v2 retrieval %s failed: %s", key, value)
            v2_results[key] = None
            if key in _V2_FAILURE_MAP:
                partial_failures.append(_V2_FAILURE_MAP[key])
        else:
            v2_results[key] = value

    # Step 3: Calculate development potential.
    # Zoning standards come from the precomputed cache (built off-box with the
    # reranker on) — the live reranker is never invoked on the report path. A cache
    # miss/stale returns None and drops into the same R1 table fallback below.
    standards = get_cached_zoning_standards(zone_class)
    # R1: when extraction is unavailable or low-confidence, fall back to the
    # deterministic Title 17 zone-class table so we never dump wrong-chapter raw
    # code and development potential can still be computed for known zones.
    if zone_class and (standards is None or standards.extraction_confidence == "low"):
        from backend.zoning_extract import standards_from_definitions
        fallback_standards = standards_from_definitions(zone_class)
        if fallback_standards is not None:
            standards = fallback_standards
    dev_potential = None
    if standards and ctx.property:
        land_sqft = ctx.property.land_sqft or 0
        bldg_sqft = ctx.property.bldg_sqft or 0
        if land_sqft > 0:
            dev_potential = calculate_development_potential(standards, land_sqft, bldg_sqft)

    # Step 4: Market value, effective tax rate, and annual-tax fallback (Q6).
    effective_tax_rate, market_value, assessment_level = _resolve_market_value_and_tax(ctx.property)

    # Step 5: Static map URL
    mapbox_token = settings.mapbox_token or settings.vite_mapbox_token
    static_map_url = None
    if mapbox_token:
        static_map_url = (
            f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/"
            f"pin-l+2563eb({resolved_lon},{resolved_lat})/"
            f"{resolved_lon},{resolved_lat},15/600x400@2x"
            f"?access_token={mapbox_token}"
        )

    # Step 6: Build bulk standards text fallback (for low-confidence extraction)
    bulk_standards_text = ""
    if zone_class:
        try:
            chunks = await _limited(
                semantic_search(
                    f"{zone_class} bulk standards floor area ratio height setback lot coverage",
                    top_k=5,
                )
            )
            if chunks:
                bulk_standards_text = "\n\n".join(
                    f"[{c.section_title}]\n{c.text}" for c in chunks[:3]
                )
        except Exception:
            pass

    # Build comparable sales summary
    comps_data = v2_results.get("comparable_sales") or {"summary": {}, "sales": []}
    comps_summary = None
    if comps_data.get("sales"):
        s = comps_data["summary"]
        comps_summary = ComparablesSummary(
            median_sale_price=s.get("median_sale_price"),
            median_price_per_land_sqft=s.get("median_price_per_land_sqft"),
            median_price_per_bldg_sqft=s.get("median_price_per_bldg_sqft"),
            price_range_min=s.get("price_range_min"),
            price_range_max=s.get("price_range_max"),
            sales_volume=s.get("sales_volume", 0),
            comp_basis=s.get("comp_basis"),
            sales=[ComparableSale(**sale) for sale in comps_data["sales"]],
        )

    # Build nearby development
    nc_data = v2_results.get("nearby_construction")
    nearby_dev = None
    if nc_data:
        projects = nc_data.get("recent_projects", [])
        projects = _enrich_nearby_projects(resolved_lat, resolved_lon, projects)
        nearby_dev = NearbyDevelopment(
            new_construction_count=nc_data.get("new_construction_count", 0),
            demolition_count=nc_data.get("demolition_count", 0),
            new_construction_cost=nc_data.get("new_construction_cost", 0.0),
            recent_projects=projects,
        )

    # Generate comparable sales chart + map
    comps_chart_b64 = None
    comps_map_b64 = None
    if comps_summary and comps_summary.sales and len(comps_summary.sales) >= 2:
        loop = asyncio.get_running_loop()
        try:
            comps_chart_b64 = await loop.run_in_executor(
                None, _generate_comps_chart, comps_summary
            )
        except Exception:
            log.warning("Failed to generate comps chart", exc_info=True)

    # Fetch basemaps for maps (zoom 15 for zoning, zoom 14 for construction)
    basemap_bytes = None
    basemap_wide_bytes = None
    if mapbox_token:
        try:
            async with httpx.AsyncClient(timeout=15) as map_client:
                basemap_url = (
                    f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/"
                    f"{resolved_lon},{resolved_lat},15/600x400@2x"
                    f"?access_token={mapbox_token}"
                )
                basemap_wide_url = (
                    f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/"
                    f"{resolved_lon},{resolved_lat},14/600x400@2x"
                    f"?access_token={mapbox_token}"
                )
                resp, resp_wide = await asyncio.gather(
                    map_client.get(basemap_url),
                    map_client.get(basemap_wide_url),
                )
                if resp.status_code == 200:
                    basemap_bytes = resp.content
                if resp_wide.status_code == 200:
                    basemap_wide_bytes = resp_wide.content
        except Exception:
            log.warning("Failed to fetch basemap for report maps", exc_info=True)

    # Fetch overlay GeoJSON for zoning map boundaries
    overlay_geojson = None
    _OVERLAY_MAP_LAYERS = [2, 5, 6, 7, 8, 9, 23]  # PD, landmark, historic, landmark bldg, nat'l register, special, SSA
    try:
        from backend.retrieval.regulatory.overlays import overlay_geojson_features
        overlay_geojson = await _limited(overlay_geojson_features(resolved_lat, resolved_lon, _OVERLAY_MAP_LAYERS))
    except Exception:
        log.warning("Failed to fetch overlay GeoJSON for zoning map", exc_info=True)

    # Generate zoning map
    zoning_map_b64 = None
    ca = base.get("community_area")
    if ca and basemap_bytes:
        try:
            from backend.retrieval.zoning import zoning_polygons_for_map
            zoning_geojson = await _limited(zoning_polygons_for_map(ca))
            if zoning_geojson.get("features"):
                loop = asyncio.get_running_loop()
                zoning_map_b64 = await loop.run_in_executor(
                    None,
                    _generate_zoning_map,
                    resolved_lat, resolved_lon,
                    zoning_geojson, basemap_bytes,
                    overlay_geojson,
                )
        except Exception:
            log.warning("Failed to generate zoning map", exc_info=True)

    # Generate construction/demolition map (wider zoom for 0.5mi radius)
    construction_map_b64 = None
    construction_basemap = basemap_wide_bytes or basemap_bytes
    if construction_basemap and nearby_dev and nearby_dev.recent_projects:
        try:
            loop = asyncio.get_running_loop()
            construction_map_b64 = await loop.run_in_executor(
                None,
                _generate_construction_map,
                resolved_lat, resolved_lon,
                nearby_dev.recent_projects, construction_basemap,
            )
        except Exception:
            log.warning("Failed to generate construction map", exc_info=True)

    # Generate comparable sales map
    if basemap_bytes and comps_summary and comps_summary.sales and len(comps_summary.sales) >= 2:
        try:
            loop = asyncio.get_running_loop()
            comps_map_b64 = await loop.run_in_executor(
                None, _generate_comps_map,
                resolved_lat, resolved_lon,
                comps_summary.sales, basemap_bytes,
            )
        except Exception:
            log.warning("Failed to generate comps map", exc_info=True)

    # Assessment trend analysis
    assessment_trend = None
    if ctx.property and ctx.property.assessment_history:
        assessment_trend = _compute_assessment_trend(ctx.property.assessment_history)

    # Ownership signals
    ownership_signals: list[dict] = []
    if ctx.property:
        ownership_signals = _derive_ownership_signals(ctx.property)

    # Parcel map + dimensions
    parcel_map_b64 = None
    parcel_dimensions = None
    if ctx.property and ctx.property.parcel_geometry:
        parcel_dimensions = _compute_parcel_dimensions(ctx.property.parcel_geometry)
        if basemap_bytes:
            # Fetch a higher-zoom basemap for the parcel map
            parcel_basemap_bytes = None
            if mapbox_token:
                parcel_basemap_url = (
                    f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/"
                    f"{resolved_lon},{resolved_lat},19/600x400@2x"
                    f"?access_token={mapbox_token}"
                )
                try:
                    parcel_resp = await httpx.AsyncClient(timeout=15).get(parcel_basemap_url)
                    if parcel_resp.status_code == 200:
                        parcel_basemap_bytes = parcel_resp.content
                except Exception:
                    log.warning("Failed to fetch parcel basemap", exc_info=True)
            if parcel_basemap_bytes:
                try:
                    loop = asyncio.get_running_loop()
                    parcel_map_b64 = await loop.run_in_executor(
                        None, _generate_parcel_map,
                        resolved_lat, resolved_lon,
                        ctx.property.parcel_geometry, parcel_basemap_bytes,
                        parcel_dimensions,
                    )
                except Exception:
                    log.warning("Failed to generate parcel map", exc_info=True)
                finally:
                    # Zoom-19 retina PNG, not returned to the caller — free it once
                    # the parcel map is rendered rather than holding it to function end.
                    del parcel_basemap_bytes

    # Zone class definitions (deterministic lookup, no API call)
    from backend.retrieval.zoning_definitions import collect_report_zone_definitions
    adj_zoning = v2_results.get("adjacent_zoning") or {}
    zone_defs = collect_report_zone_definitions(zone_class, adj_zoning)
    zone_definitions_data = [
        {
            "zone_class": zd.zone_class,
            "name": zd.name,
            "code_section": zd.code_section,
            "far": zd.far,
            "max_height": zd.max_height,
            "lot_coverage": zd.lot_coverage,
            "uses": zd.uses,
            "notes": zd.notes,
            "is_fallback": zd.is_fallback,
        }
        for zd in zone_defs
    ]

    report = ReportData(
        address=resolved_address,
        lat=resolved_lat,
        lon=resolved_lon,
        community_area=base.get("community_area"),
        community_area_name=base.get("community_area_name"),
        context=ctx,
        zoning_standards=standards,
        development_potential=dev_potential,
        comparables=comps_summary,
        address_permits=v2_results.get("address_permits") or [],
        address_violations=v2_results.get("address_violations") or [],
        adjacent_zoning=adj_zoning,
        nearby_development=nearby_dev,
        effective_tax_rate=effective_tax_rate,
        market_value=market_value,
        assessment_level=assessment_level,
        assessment_trend=assessment_trend,
        ownership_signals=ownership_signals,
        parcel_map_b64=parcel_map_b64,
        parcel_dimensions=parcel_dimensions,
        static_map_url=static_map_url,
        comps_chart_b64=comps_chart_b64,
        comps_map_b64=comps_map_b64,
        zoning_map_b64=zoning_map_b64,
        construction_map_b64=construction_map_b64,
        bulk_standards_text=bulk_standards_text,
        zone_definitions=zone_definitions_data,
        partial_failures=partial_failures,
        resolved_pin=pin,
        resolved_confidence=confidence,
    )
    # Set the render language before synthesis so the deterministic narrative
    # builders below localize their output (they read report.language). No LLM.
    from backend import report_i18n
    report.language = report_i18n.normalize_lang(language)

    # V5 synthesis (all deterministic, no API calls). far_utilization comes
    # first: it only needs property + standards, and the opportunities pass
    # reads it — one utilization computation instead of a drift-prone inline
    # twin (2026-07-06 audit).
    report.far_utilization = _compute_far_utilization(report)
    report.opportunities, report.constraints = _synthesize_opportunities_constraints(report)
    report.estimated_land_value = _compute_land_value_range(report)
    report.approval_pathway = _compute_approval_pathway(report)
    report.development_trend = _compute_development_trend(report)
    report.incentive_stacking_narrative = _build_incentive_stacking_narrative(report)
    report.envelope_summary = _build_envelope_summary(report)

    # Phase 3 decision-quality synthesis (depends on the V5 fields above)
    report.unit_yield = _compute_unit_yield(report)
    report.comp_valuation = _compute_comp_valuation(report)
    report.ownership_interpretation = _ownership_interpretation(report)
    report.decision_box = _build_decision_box(report)

    # Envelope map (CPU-bound matplotlib render)
    if ctx.property and ctx.property.parcel_geometry and standards:
        try:
            loop = asyncio.get_running_loop()
            env_b64, env_sqft = await loop.run_in_executor(
                None, _generate_envelope_map,
                resolved_lat, resolved_lon,
                ctx.property.parcel_geometry, standards,
                parcel_dimensions,
            )
            report.envelope_map_b64 = env_b64
            report.buildable_footprint_sqft = env_sqft
        except Exception:
            log.warning("Failed to generate envelope map", exc_info=True)

    return report, basemap_bytes, basemap_wide_bytes


def _enrich_nearby_projects(
    lat: float, lon: float, projects: list[dict],
) -> list[dict]:
    """Add distance_mi and formatted_address to each nearby project."""
    from backend.retrieval.property.sales import _haversine_mi
    enriched = []
    for proj in projects:
        p = dict(proj)
        try:
            plat = float(p.get("latitude", 0))
            plon = float(p.get("longitude", 0))
            if plat and plon:
                p["distance_mi"] = round(_haversine_mi(lat, lon, plat, plon), 2)
        except (ValueError, TypeError):
            pass
        parts = []
        if p.get("street_number"):
            parts.append(str(p["street_number"]))
        if p.get("street_direction"):
            parts.append(str(p["street_direction"]))
        if p.get("street_name"):
            parts.append(str(p["street_name"]))
        if parts:
            p["formatted_address"] = " ".join(parts)
        enriched.append(p)
    enriched.sort(key=lambda x: x.get("distance_mi", 999))
    return enriched


def _compute_assessment_trend(
    assessment_history: list,
) -> dict | None:
    """Compute assessment trend from assessment history records."""
    valid = [a for a in assessment_history if a.total and a.total > 0 and a.year]
    if len(valid) < 2:
        return None
    valid.sort(key=lambda a: a.year)
    oldest, newest = valid[0], valid[-1]
    years = newest.year - oldest.year
    if years <= 0:
        return None
    total_change_pct = round((newest.total - oldest.total) / oldest.total * 100, 1)
    cagr_pct = round(((newest.total / oldest.total) ** (1.0 / years) - 1) * 100, 1)
    direction = "increasing" if total_change_pct > 5 else "decreasing" if total_change_pct < -5 else "stable"
    return {
        "total_change_pct": total_change_pct,
        "cagr_pct": cagr_pct,
        "years": years,
        "oldest_year": oldest.year,
        "newest_year": newest.year,
        "oldest_total": oldest.total,
        "newest_total": newest.total,
        "direction": direction,
    }


def _derive_ownership_signals(prop) -> list[dict]:
    """Derive factual ownership signals from property data. No LLM."""
    if not prop:
        return []
    signals: list[dict] = []

    if prop.sales_history:
        sorted_sales = sorted(
            [s for s in prop.sales_history if s.date],
            key=lambda s: s.date, reverse=True,
        )
        if sorted_sales:
            last_sale = sorted_sales[0]
            from datetime import date
            try:
                sale_date = date.fromisoformat(last_sale.date[:10])
                years_held = round((date.today() - sale_date).days / 365.25, 1)
                if years_held > 10:
                    signals.append({
                        "signal": "Long-Term Hold",
                        "detail": f"Last sale {years_held:.0f} years ago ({last_sale.date[:10]})",
                        "category": "ownership_duration",
                    })
                elif years_held < 2:
                    signals.append({
                        "signal": "Recent Acquisition",
                        "detail": f"Acquired {years_held:.1f} years ago ({last_sale.date[:10]})",
                        "category": "ownership_duration",
                    })
                else:
                    signals.append({
                        "signal": "Ownership Duration",
                        "detail": f"{years_held:.0f} years since last sale ({last_sale.date[:10]})",
                        "category": "ownership_duration",
                    })
            except (ValueError, TypeError):
                pass

            if last_sale.price is not None and last_sale.price <= 500:
                signals.append({
                    "signal": "Non-Arm's-Length Transfer",
                    "detail": f"Last sale price ${last_sale.price:,.0f} suggests related-party transfer",
                    "category": "transfer_type",
                })
            elif last_sale.deed_type and "QUIT" in last_sale.deed_type.upper():
                signals.append({
                    "signal": "Quit Claim Deed",
                    "detail": "Last transfer via quit claim deed (non-arm's-length)",
                    "category": "transfer_type",
                })

        if len(sorted_sales) >= 2:
            for i in range(len(sorted_sales) - 1):
                try:
                    d1 = date.fromisoformat(sorted_sales[i].date[:10])
                    d2 = date.fromisoformat(sorted_sales[i + 1].date[:10])
                    gap_years = (d1 - d2).days / 365.25
                    if gap_years < 2:
                        signals.append({
                            "signal": "Rapid Turnover",
                            "detail": f"Consecutive sales {gap_years:.1f} years apart ({sorted_sales[i+1].date[:10]} → {sorted_sales[i].date[:10]})",
                            "category": "turnover",
                        })
                        break
                except (ValueError, TypeError):
                    continue

    # Exemptions live in tax_exemptions (PTAXSIM exe_* columns → kind labels).
    # The old check scanned tax_breakdown AGENCY names for "HOMEOWNER" — those
    # are taxing districts (City of Chicago, Board of Education…), so the
    # signal could never fire (2026-07-06 audit).
    if any(e.kind == "Homeowner" for e in (prop.tax_exemptions or [])):
        signals.append({
            "signal": "Owner-Occupied (Homeowner Exemption)",
            "detail": "Homeowner exemption claimed on the tax bill",
            "category": "occupancy",
        })

    return signals


def _compute_parcel_dimensions(geojson_polygon: dict) -> dict | None:
    """Compute parcel dimensions from GeoJSON polygon."""
    import math
    coords = None
    geom_type = geojson_polygon.get("type", "")
    if geom_type == "Polygon":
        rings = geojson_polygon.get("coordinates", [])
        if rings:
            coords = rings[0]
    elif geom_type == "MultiPolygon":
        polys = geojson_polygon.get("coordinates", [])
        if polys and polys[0]:
            coords = polys[0][0]

    if not coords or len(coords) < 4:
        return None

    lat_mid = sum(c[1] for c in coords) / len(coords)
    cos_lat = math.cos(math.radians(lat_mid))

    edges = []
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        dx = (lon2 - lon1) * cos_lat * FT_PER_DEG_LAT
        dy = (lat2 - lat1) * FT_PER_DEG_LAT
        length_ft = math.sqrt(dx * dx + dy * dy)
        bearing = math.degrees(math.atan2(dx, dy)) % 360
        edges.append({"length_ft": round(length_ft, 1), "bearing": round(bearing, 1)})

    if not edges:
        return None

    # Area via shoelace formula in local feet
    xs = [(c[0] - coords[0][0]) * cos_lat * FT_PER_DEG_LAT for c in coords]
    ys = [(c[1] - coords[0][1]) * FT_PER_DEG_LAT for c in coords]
    n = len(xs)
    area = 0.0
    for i in range(n - 1):
        area += xs[i] * ys[i + 1] - xs[i + 1] * ys[i]
    area_sqft = abs(area) / 2.0

    perimeter_ft = sum(e["length_ft"] for e in edges)

    sorted_edges = sorted(edges, key=lambda e: e["length_ft"], reverse=True)
    frontage_ft = None
    depth_ft = None
    if len(sorted_edges) >= 2:
        # Group edges by similar bearing (within 15 degrees)
        long_edge = sorted_edges[0]
        perpendicular = []
        parallel = []
        for e in sorted_edges[1:]:
            angle_diff = abs(long_edge["bearing"] - e["bearing"]) % 180
            if angle_diff < 30 or angle_diff > 150:
                parallel.append(e)
            else:
                perpendicular.append(e)
        depth_ft = round(long_edge["length_ft"], 1)
        if perpendicular:
            frontage_ft = round(perpendicular[0]["length_ft"], 1)
        elif parallel:
            frontage_ft = round(parallel[0]["length_ft"], 1)

    return {
        "area_sqft": round(area_sqft, 0),
        "perimeter_ft": round(perimeter_ft, 1),
        "frontage_ft": frontage_ft,
        "depth_ft": depth_ft,
        "edge_count": len(edges),
        "edges": edges[:8],
    }


def _generate_parcel_map(
    lat: float,
    lon: float,
    parcel_geojson: dict,
    basemap_bytes: bytes,
    dimensions: dict | None = None,
) -> str | None:
    """Generate a base64-encoded PNG map with parcel polygon overlay.

    Uses zoom 19 so the lot boundary fills the frame. Draws the parcel
    boundary, labels each edge with its length, and adds a scale bar.
    """
    import base64
    import io
    from math import atan2, degrees

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MplPolygon
        from PIL import Image
    except ImportError:
        return None

    MAP_W, MAP_H, ZOOM = 600, 400, 19

    try:
        basemap = Image.open(io.BytesIO(basemap_bytes))
        img_w, img_h = basemap.size

        dpi = 150
        fig, ax = plt.subplots(figsize=(img_w / dpi, img_h / dpi), dpi=dpi)
        ax.imshow(basemap, extent=[0, img_w, img_h, 0], aspect="auto")
        ax.set_xlim(0, img_w)
        ax.set_ylim(img_h, 0)
        ax.axis("off")

        geom_type = parcel_geojson.get("type", "")
        coord_rings: list[list] = []
        if geom_type == "Polygon":
            coord_rings = parcel_geojson.get("coordinates", [])
        elif geom_type == "MultiPolygon":
            for poly in parcel_geojson.get("coordinates", []):
                coord_rings.extend(poly)

        for ring in coord_rings:
            pixels = []
            for coord in ring:
                px, py = _latlon_to_px(coord[1], coord[0], lat, lon, ZOOM, MAP_W, MAP_H)
                pixels.append((px, py))
            if len(pixels) < 3:
                continue

            # Fill + thick boundary
            patch = MplPolygon(
                pixels, closed=True,
                facecolor=(0.15, 0.39, 0.92, 0.15),
                edgecolor=(0.15, 0.39, 0.92, 1.0),
                linewidth=3,
            )
            ax.add_patch(patch)

            # Corner markers
            for px_pt, py_pt in pixels[:-1]:
                ax.plot(px_pt, py_pt, "s", markersize=4,
                        color="#2563eb", markeredgecolor="white",
                        markeredgewidth=0.8, zorder=12)

            # Edge dimension labels — offset outward from centroid
            if dimensions and len(pixels) >= 4:
                cx = sum(p[0] for p in pixels[:-1]) / max(len(pixels) - 1, 1)
                cy = sum(p[1] for p in pixels[:-1]) / max(len(pixels) - 1, 1)
                edges = dimensions.get("edges", [])
                for i in range(min(len(pixels) - 1, len(edges))):
                    x1, y1 = pixels[i]
                    x2, y2 = pixels[i + 1]
                    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                    length = edges[i]["length_ft"]
                    if length < 5:
                        continue
                    # Push label outward from polygon centroid
                    dx, dy = mx - cx, my - cy
                    norm = (dx**2 + dy**2) ** 0.5 or 1
                    offset = 28
                    lx = mx + dx / norm * offset
                    ly = my + dy / norm * offset

                    # Rotate text to match edge angle
                    angle = degrees(atan2(-(y2 - y1), x2 - x1))
                    if angle > 90:
                        angle -= 180
                    elif angle < -90:
                        angle += 180

                    ax.text(
                        lx, ly, f"{length:.0f} ft",
                        ha="center", va="center", fontsize=7,
                        color="white", fontweight="bold",
                        rotation=angle,
                        bbox=dict(facecolor="#2563eb", alpha=0.9,
                                  edgecolor="white", linewidth=0.5,
                                  pad=2.5, boxstyle="round,pad=0.3"),
                        zorder=15,
                    )

        # Info box: frontage x depth = area
        if dimensions:
            info_parts = []
            if dimensions.get("frontage_ft"):
                info_parts.append(f"Frontage: {dimensions['frontage_ft']:.0f} ft")
            if dimensions.get("depth_ft"):
                info_parts.append(f"Depth: {dimensions['depth_ft']:.0f} ft")
            if dimensions.get("area_sqft"):
                info_parts.append(f"Area: {dimensions['area_sqft']:,.0f} sq ft")
            if info_parts:
                ax.text(
                    8, 12, "  |  ".join(info_parts),
                    ha="left", va="top", fontsize=6, color="white",
                    bbox=dict(facecolor="#1a1a1a", alpha=0.85,
                              edgecolor="#444", linewidth=0.5,
                              pad=4, boxstyle="round,pad=0.3"),
                    zorder=20,
                )

        # Scale bar (bottom-left)
        from math import cos, radians
        meters_per_px = 156543.03 * cos(radians(lat)) / (2 ** ZOOM) / 2  # @2x
        ft_per_px = meters_per_px * 3.28084
        bar_ft = 50
        bar_px = bar_ft / ft_per_px
        bar_x, bar_y = 30, img_h - 40
        ax.plot([bar_x, bar_x + bar_px], [bar_y, bar_y],
                color="white", linewidth=2.5, solid_capstyle="butt", zorder=18)
        ax.plot([bar_x, bar_x], [bar_y - 4, bar_y + 4],
                color="white", linewidth=1.5, zorder=18)
        ax.plot([bar_x + bar_px, bar_x + bar_px], [bar_y - 4, bar_y + 4],
                color="white", linewidth=1.5, zorder=18)
        ax.text(bar_x + bar_px / 2, bar_y - 8, f"{bar_ft} ft",
                ha="center", va="bottom", fontsize=5.5, color="white",
                fontweight="bold", zorder=18)

        ax.text(
            img_w / 2, img_h - 8,
            "Sources: Cook County GIS · Mapbox · OpenStreetMap",
            ha="center", va="bottom", fontsize=4.5, color="#999999",
            bbox=dict(facecolor="#0d0d0d", alpha=0.7, edgecolor="none", pad=3),
            zorder=15,
        )

        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight",
                    pad_inches=0, facecolor="#0d0d0d")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("ascii")

    except Exception:
        log.warning("Failed to generate parcel map", exc_info=True)
        return None


def _classify_edges(
    coords: list[list[float]],
    front_ft: int, side_ft: int, rear_ft: int,
) -> list[dict]:
    """Classify polygon edges as front/side/rear for setback drawing.

    Heuristic for Chicago's grid: the shortest pair of roughly-parallel edges
    are front/rear (lot width), the longest pair are sides (lot depth).
    Front = shorter of the width pair (street-facing).
    """
    import math

    if len(coords) < 4:
        return []

    lat_mid = sum(c[1] for c in coords) / len(coords)
    cos_lat = math.cos(math.radians(lat_mid))

    edges = []
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        dx = (lon2 - lon1) * cos_lat * FT_PER_DEG_LAT
        dy = (lat2 - lat1) * FT_PER_DEG_LAT
        length_ft = math.sqrt(dx * dx + dy * dy)
        bearing = math.degrees(math.atan2(dx, dy)) % 360
        # Inward normal (perpendicular, pointing into polygon center)
        cx = sum(c[0] for c in coords[:-1]) / (len(coords) - 1)
        cy = sum(c[1] for c in coords[:-1]) / (len(coords) - 1)
        mx = (lon1 + lon2) / 2
        my = (lat1 + lat2) / 2
        # Two candidate normals
        nx1, ny1 = -dy, dx
        nx2, ny2 = dy, -dx
        # Pick the one pointing toward centroid
        to_cx = (cx - mx) * cos_lat * FT_PER_DEG_LAT
        to_cy = (cy - my) * FT_PER_DEG_LAT
        if nx1 * to_cx + ny1 * to_cy > nx2 * to_cx + ny2 * to_cy:
            nx, ny = nx1, ny1
        else:
            nx, ny = nx2, ny2
        norm = math.sqrt(nx * nx + ny * ny)
        if norm > 0:
            nx /= norm
            ny /= norm

        edges.append({
            "idx": i,
            "p1": coords[i], "p2": coords[i + 1],
            "length_ft": length_ft,
            "bearing": bearing,
            "nx_ft": nx, "ny_ft": ny,
        })

    if len(edges) < 3:
        # Fallback: uniform minimum setback
        min_sb = min(front_ft, side_ft, rear_ft)
        for e in edges:
            e["role"] = "uniform"
            e["setback_ft"] = min_sb
        return edges

    # Normalize bearing to 0-180 (undirected)
    for e in edges:
        e["norm_bearing"] = e["bearing"] % 180

    # Sort by length to find the two principal directions
    by_length = sorted(edges, key=lambda e: e["length_ft"], reverse=True)

    # Group into two bearing clusters using the longest edge as anchor
    anchor_bearing = by_length[0]["norm_bearing"]
    group_a = []  # Parallel to anchor (sides / depth)
    group_b = []  # Perpendicular to anchor (front / rear width)

    for e in edges:
        diff = abs(e["norm_bearing"] - anchor_bearing) % 180
        if diff > 90:
            diff = 180 - diff
        if diff < 30:
            group_a.append(e)
        else:
            group_b.append(e)

    # If grouping failed (irregular lot), use uniform setback
    if not group_a or not group_b:
        min_sb = min(front_ft, side_ft, rear_ft)
        for e in edges:
            e["role"] = "uniform"
            e["setback_ft"] = min_sb
        return edges

    # group_a = longer edges = sides, group_b = shorter edges = front/rear
    # But if group_b is actually longer, swap
    avg_a = sum(e["length_ft"] for e in group_a) / len(group_a)
    avg_b = sum(e["length_ft"] for e in group_b) / len(group_b)
    if avg_b > avg_a:
        group_a, group_b = group_b, group_a

    for e in group_a:
        e["role"] = "side"
        e["setback_ft"] = side_ft

    # In group_b, shortest = front, rest = rear
    group_b.sort(key=lambda e: e["length_ft"])
    for i, e in enumerate(group_b):
        if i == 0:
            e["role"] = "front"
            e["setback_ft"] = front_ft
        else:
            e["role"] = "rear"
            e["setback_ft"] = rear_ft

    return edges


def _compute_inset_polygon(
    coords: list[list[float]],
    edges: list[dict],
) -> tuple[list[tuple[float, float]], float] | None:
    """Compute the buildable footprint polygon by insetting each edge.

    CONVEX-ONLY method: adjacent offset lines are intersected pairwise —
    exact for rectangular Chicago lots, but a concave (L-shaped) parcel can
    yield a self-intersecting "footprint" with a nonsense shoelace area. The
    inset-smaller-than-parcel check at the end rejects the gross failures;
    a shapely buffer-based inset is the upgrade path if irregular lots ever
    matter here.
    """
    import math

    if not edges or len(coords) < 4:
        return None

    lat_mid = sum(c[1] for c in coords) / len(coords)
    cos_lat = math.cos(math.radians(lat_mid))
    ft_to_lon = 1.0 / (cos_lat * FT_PER_DEG_LAT)
    ft_to_lat = 1.0 / FT_PER_DEG_LAT

    # For each edge, compute the offset line (shifted inward by setback)
    offset_lines = []
    for e in edges:
        sb = e.get("setback_ft", 0)
        if sb <= 0:
            # No setback — keep original edge
            offset_lines.append((e["p1"], e["p2"]))
            continue
        # Offset in lon/lat space
        dx_lon = e["nx_ft"] * sb * ft_to_lon
        dy_lat = e["ny_ft"] * sb * ft_to_lat
        p1_off = [e["p1"][0] + dx_lon, e["p1"][1] + dy_lat]
        p2_off = [e["p2"][0] + dx_lon, e["p2"][1] + dy_lat]
        offset_lines.append((p1_off, p2_off))

    if len(offset_lines) < 3:
        return None

    # Intersect adjacent offset lines to find inner polygon vertices
    def line_intersect(p1, p2, p3, p4):
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        x4, y4 = p4
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-15:
            return None
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        ix = x1 + t * (x2 - x1)
        iy = y1 + t * (y2 - y1)
        return (ix, iy)

    inner_pts = []
    n = len(offset_lines)
    for i in range(n):
        j = (i + 1) % n
        pt = line_intersect(
            offset_lines[i][0], offset_lines[i][1],
            offset_lines[j][0], offset_lines[j][1],
        )
        if pt is None:
            return None
        inner_pts.append(pt)

    # Close the polygon
    if inner_pts and inner_pts[0] != inner_pts[-1]:
        inner_pts.append(inner_pts[0])

    # Compute area via shoelace in feet
    xs = [(p[0] - inner_pts[0][0]) * cos_lat * FT_PER_DEG_LAT for p in inner_pts]
    ys = [(p[1] - inner_pts[0][1]) * FT_PER_DEG_LAT for p in inner_pts]
    area = 0.0
    for i in range(len(xs) - 1):
        area += xs[i] * ys[i + 1] - xs[i + 1] * ys[i]
    area_sqft = abs(area) / 2.0

    if area_sqft < 10:
        return None

    # Sanity: an inset polygon can never out-measure its parcel. A larger
    # "footprint" means the pairwise-intersection method self-intersected
    # (concave lot) — return None rather than print a fabricated number.
    pxs = [(c[0] - coords[0][0]) * cos_lat * FT_PER_DEG_LAT for c in coords]
    pys = [(c[1] - coords[0][1]) * FT_PER_DEG_LAT for c in coords]
    parcel_area = 0.0
    for i in range(len(pxs) - 1):
        parcel_area += pxs[i] * pys[i + 1] - pxs[i + 1] * pys[i]
    parcel_area_sqft = abs(parcel_area) / 2.0
    if parcel_area_sqft > 0 and area_sqft >= parcel_area_sqft:
        return None

    return inner_pts, area_sqft


def _generate_envelope_map(
    lat: float, lon: float,
    parcel_geojson: dict,
    standards: "ZoningStandards",
    dimensions: dict | None = None,
) -> tuple[str | None, float | None]:
    """Render parcel with setback zones and buildable footprint.

    Returns (base64_png, buildable_footprint_sqft) or (None, None).
    """
    import base64
    import io

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MplPolygon
    except ImportError:
        return None, None

    front_ft = standards.front_setback_ft or 0
    side_ft = standards.side_setback_ft or 0
    rear_ft = standards.rear_setback_ft or 0

    if front_ft == 0 and side_ft == 0 and rear_ft == 0:
        return None, None

    # Extract coordinates
    geom_type = parcel_geojson.get("type", "")
    coords = None
    if geom_type == "Polygon":
        rings = parcel_geojson.get("coordinates", [])
        if rings:
            coords = rings[0]
    elif geom_type == "MultiPolygon":
        polys = parcel_geojson.get("coordinates", [])
        if polys and polys[0]:
            coords = polys[0][0]

    if not coords or len(coords) < 4:
        return None, None

    edges = _classify_edges(coords, front_ft, side_ft, rear_ft)
    if not edges:
        return None, None

    inset_result = _compute_inset_polygon(coords, edges)
    if inset_result is None:
        return None, None

    inner_pts, buildable_sqft = inset_result

    try:
        import math

        lat_mid = sum(c[1] for c in coords) / len(coords)
        cos_lat = math.cos(math.radians(lat_mid))

        # Convert to local feet for rendering
        def to_ft(lon_v, lat_v):
            return (
                (lon_v - coords[0][0]) * cos_lat * FT_PER_DEG_LAT,
                (lat_v - coords[0][1]) * FT_PER_DEG_LAT,
            )

        parcel_ft = [to_ft(c[0], c[1]) for c in coords]
        inner_ft = [to_ft(p[0], p[1]) for p in inner_pts]

        # Figure size based on parcel extents
        all_x = [p[0] for p in parcel_ft]
        all_y = [p[1] for p in parcel_ft]
        w = max(all_x) - min(all_x)
        h = max(all_y) - min(all_y)
        pad = max(w, h) * 0.15

        dpi = 150
        fig_w = max(3, min(5, (w + 2 * pad) / 40))
        fig_h = max(3, min(5, (h + 2 * pad) / 40))
        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
        ax.set_facecolor("#f8fafc")
        fig.set_facecolor("#f8fafc")

        # Parcel outline
        parcel_patch = MplPolygon(
            parcel_ft, closed=True,
            facecolor="#f3f4f6", edgecolor="#374151",
            linewidth=2, zorder=2,
        )
        ax.add_patch(parcel_patch)

        # Setback zone hatching — draw parcel minus inner as a visual
        # Simpler approach: draw hatched strips for each edge
        for e in edges:
            sb = e.get("setback_ft", 0)
            if sb <= 0:
                continue
            p1_ft = to_ft(e["p1"][0], e["p1"][1])
            p2_ft = to_ft(e["p2"][0], e["p2"][1])
            # Offset points
            ft_to_lon = 1.0 / (cos_lat * FT_PER_DEG_LAT)
            ft_to_lat = 1.0 / FT_PER_DEG_LAT
            dx_lon = e["nx_ft"] * sb * ft_to_lon
            dy_lat = e["ny_ft"] * sb * ft_to_lat
            p1_off_ft = to_ft(e["p1"][0] + dx_lon, e["p1"][1] + dy_lat)
            p2_off_ft = to_ft(e["p2"][0] + dx_lon, e["p2"][1] + dy_lat)

            strip = [p1_ft, p2_ft, p2_off_ft, p1_off_ft]
            strip_patch = MplPolygon(
                strip, closed=True,
                facecolor="#e5e7eb", edgecolor="none",
                alpha=0.6, hatch="///", zorder=3,
            )
            ax.add_patch(strip_patch)

            # Label the setback
            mx = (p1_ft[0] + p2_ft[0] + p1_off_ft[0] + p2_off_ft[0]) / 4
            my = (p1_ft[1] + p2_ft[1] + p1_off_ft[1] + p2_off_ft[1]) / 4
            role = e.get("role", "")
            label = f"{sb}' {role}" if role and role != "uniform" else f"{sb}'"
            ax.text(
                mx, my, label,
                ha="center", va="center", fontsize=6,
                color="#6b7280", fontstyle="italic",
                zorder=8,
            )

        # Buildable footprint
        inner_patch = MplPolygon(
            inner_ft, closed=True,
            facecolor=(0.15, 0.39, 0.92, 0.15),
            edgecolor="#2563eb",
            linewidth=1.5, linestyle="--",
            zorder=5,
        )
        ax.add_patch(inner_patch)

        # Buildable area annotation centered
        cx = sum(p[0] for p in inner_ft) / len(inner_ft)
        cy = sum(p[1] for p in inner_ft) / len(inner_ft)
        ax.text(
            cx, cy, f"~{buildable_sqft:,.0f} sq ft\nbuildable",
            ha="center", va="center", fontsize=7,
            color="#1e40af", fontweight="bold",
            bbox=dict(facecolor="white", alpha=0.85, edgecolor="#93c5fd",
                      pad=3, boxstyle="round,pad=0.3"),
            zorder=10,
        )

        # Edge dimension labels on parcel outline (outside edge)
        for e in edges:
            if e["length_ft"] < 5:
                continue
            p1_ft = to_ft(e["p1"][0], e["p1"][1])
            p2_ft = to_ft(e["p2"][0], e["p2"][1])
            mx = (p1_ft[0] + p2_ft[0]) / 2
            my = (p1_ft[1] + p2_ft[1]) / 2
            # Push dimension label outward past the edge
            ox = -e["nx_ft"] * 10
            oy = -e["ny_ft"] * 10
            ax.text(
                mx + ox, my + oy, f"{e['length_ft']:.0f}'",
                ha="center", va="center", fontsize=5.5,
                color="#374151", fontweight="bold",
                bbox=dict(facecolor="white", alpha=0.9, edgecolor="#d1d5db",
                          pad=1.5, boxstyle="round,pad=0.2"),
                zorder=9,
            )

        ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
        ax.set_ylim(min(all_y) - pad, max(all_y) + pad)
        ax.set_aspect("equal")
        ax.axis("off")

        # Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="#f3f4f6", edgecolor="#374151", linewidth=1.5, label="Parcel"),
            Patch(facecolor="#e5e7eb", edgecolor="none", hatch="///", alpha=0.6, label="Setback zone"),
            Patch(facecolor=(0.15, 0.39, 0.92, 0.15), edgecolor="#2563eb",
                  linestyle="--", linewidth=1, label="Buildable footprint"),
        ]
        ax.legend(handles=legend_elements, loc="upper right", fontsize=5,
                  framealpha=0.9, edgecolor="#d1d5db")

        fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight",
                    pad_inches=0.1, facecolor="#f8fafc")
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("ascii")
        return b64, round(buildable_sqft, 0)

    except Exception:
        log.warning("Failed to generate envelope map", exc_info=True)
        return None, None


# Conservative height-per-story estimate for the nonconformity check below.
# Chicago residential floors run ~10–12 ft floor-to-floor; using the low bound
# means we under-estimate building height and so never claim "exceeds the
# height limit" on a building that actually complies.
_EST_FT_PER_STORY = 10


def _synthesize_opportunities_constraints(
    report: "ReportData",
) -> tuple[list[dict], list[dict]]:
    """Deterministic cross-reference of all report data into actionable insights."""
    from datetime import date

    opportunities: list[dict] = []
    constraints: list[dict] = []

    ctx = report.context
    prop = ctx.property
    reg = ctx.regulatory
    inc = ctx.incentives
    nbr = ctx.neighborhood
    dev = report.development_potential
    comps = report.comparables
    standards = report.zoning_standards
    current_year = date.today().year
    t = report_i18n.make_translator(report.language)
    tn = report_i18n.make_plural(report.language)

    # --- Incentive stacking ---
    if inc:
        has_tif = inc.in_tif_district
        has_oz = inc.in_opportunity_zone
        has_ez = inc.in_enterprise_zone
        has_qct = inc.in_qct
        has_nmtc = inc.in_nmtc

        if has_tif and has_oz and has_qct:
            opportunities.append({
                "signal": t("oc.triple_stack.signal"),
                "detail": t("oc.triple_stack.detail"),
                "category": "incentive",
            })
        elif has_tif and has_oz:
            opportunities.append({
                "signal": t("oc.tif_oz.signal"),
                "detail": t("oc.tif_oz.detail"),
                "category": "incentive",
            })
        elif has_oz and has_qct:
            opportunities.append({
                "signal": t("oc.oz_qct.signal"),
                "detail": t("oc.oz_qct.detail"),
                "category": "incentive",
            })

        if has_tif and has_ez:
            opportunities.append({
                "signal": t("oc.tif_ez.signal"),
                "detail": t("oc.tif_ez.detail"),
                "category": "incentive",
            })

        if has_nmtc and inc.nmtc_severe_distress:
            opportunities.append({
                "signal": t("oc.nmtc_distress.signal"),
                "detail": t("oc.nmtc_distress.detail"),
                "category": "incentive",
            })

        if has_oz and prop and (prop.bldg_sqft or 0) == 0:
            opportunities.append({
                "signal": t("oc.vacant_oz.signal"),
                "detail": t("oc.vacant_oz.detail"),
                "category": "incentive",
            })

        if inc.grant_programs and inc.grant_programs.total_funding and inc.grant_programs.total_funding > 500_000:
            opportunities.append({
                "signal": t("oc.grants.signal"),
                "detail": t("oc.grants.detail", funding=f"${inc.grant_programs.total_funding:,.0f}"),
                "category": "incentive",
            })

        if has_tif and inc.tif_end_year:
            years_left = inc.tif_end_year - current_year
            if 0 < years_left <= 3:
                constraints.append({
                    "signal": tn("oc.tif_expiry.signal", years_left, years=years_left),
                    "detail": t("oc.tif_expiry.detail", tif=inc.tif_name, year=inc.tif_end_year),
                    "category": "incentive",
                })

    # --- TOD & Transit ---
    if nbr and nbr.transit and nbr.transit.tod_eligible and standards and standards.parking_residential:
        opportunities.append({
            "signal": t("oc.tod_parking.signal"),
            "detail": t("oc.tod_parking.detail"),
            "category": "zoning",
        })

    if nbr and nbr.walkscore and nbr.walkscore.walk_score and nbr.walkscore.walk_score >= 80 and nbr and nbr.transit and nbr.transit.tod_eligible:
        opportunities.append({
            "signal": t("oc.walkable.signal", walk=nbr.walkscore.walk_score),
            "detail": t("oc.walkable.detail"),
            "category": "market",
        })

    if reg and any(o.layer_type == "adu" for o in (reg.overlays or [])):
        opportunities.append({
            "signal": t("oc.adu.signal"),
            "detail": t("oc.adu.detail"),
            "category": "zoning",
        })

    # --- Development potential ---
    if prop and (prop.bldg_sqft or 0) == 0 and prop.land_sqft and dev and dev.max_buildable_sqft and dev.development_surplus_sqft and dev.development_surplus_sqft > 0:
        opportunities.append({
            "signal": t("oc.vacant_full.signal"),
            "detail": t("oc.vacant_full.detail", land=f"{prop.land_sqft:,}", buildable=f"{dev.max_buildable_sqft:,}"),
            "category": "zoning",
        })

    # Single source: _compute_far_utilization (runs just before this pass) —
    # the previous inline bldg/max_buildable twin could drift from it.
    fu = report.far_utilization
    if fu and not fu["vacant"] and fu["utilization_pct"] < 30:
        opportunities.append({
            "signal": t("oc.under_improved.signal", pct=fu["utilization_pct"]),
            "detail": t("oc.under_improved.detail", existing=f"{fu['existing_sqft']:,}", pct=fu["utilization_pct"], buildable=f"{fu['allowed_sqft']:,}"),
            "category": "zoning",
        })

    if prop and prop.bldg_sqft and dev and dev.development_surplus_sqft is not None and dev.development_surplus_sqft <= 0:
        constraints.append({
            "signal": t("oc.at_far_limit.signal"),
            "detail": t("oc.at_far_limit.detail", existing=f"{prop.bldg_sqft:,}"),
            "category": "zoning",
        })

    if prop and prop.bldg_age and prop.bldg_age >= 50 and prop.bldg_sqft and prop.bldg_sqft > 0:
        opportunities.append({
            "signal": t("oc.historic_credits.signal", age=prop.bldg_age),
            "detail": t("oc.historic_credits.detail"),
            "category": "financial",
        })

    # --- Zoning conformity / nonconformity ---
    if prop and prop.year_built and prop.year_built < 1957 and prop.bldg_sqft and prop.bldg_sqft > 0:
        nonconformities: list[str] = []
        if standards and standards.far and prop.bldg_sqft and prop.land_sqft:
            allowed_sqft = standards.far * prop.land_sqft
            if prop.bldg_sqft > allowed_sqft * 1.05:
                nonconformities.append(t("oc.nonconf_floor_area", bldg=f"{prop.bldg_sqft:,}", allowed=f"{allowed_sqft:,.0f}", far=standards.far))
        if standards and standards.max_height_ft and prop.stories:
            # Deliberately LOW ft-per-story so an "exceeds the height limit"
            # claim only fires when it would survive a real measurement; the
            # limit itself is the ordinance floor tier (apply_table_authority),
            # which points the same conservative direction.
            est_height = prop.stories * _EST_FT_PER_STORY
            if est_height > standards.max_height_ft:
                nonconformities.append(t("oc.nonconf_height", stories=prop.stories, est=est_height, limit=f"{standards.max_height_ft:.0f}"))
        if nonconformities:
            opportunities.append({
                "signal": t("oc.nonconforming.signal", year=prop.year_built),
                "detail": t("oc.nonconforming.detail", year=prop.year_built, items=t("oc.nonconf_join").join(nonconformities)),
                "category": "zoning",
            })
        elif prop.year_built < 1957:
            opportunities.append({
                "signal": t("oc.pre_zoning.signal", year=prop.year_built),
                "detail": t("oc.pre_zoning.detail"),
                "category": "zoning",
            })

    # --- Regulatory ---
    if reg and reg.in_planned_development:
        constraints.append({
            "signal": t("oc.pd_discretionary.signal"),
            "detail": t("oc.pd_discretionary.detail"),
            "category": "regulatory",
        })

    if reg and reg.in_landmark_district:
        constraints.append({
            "signal": t("oc.landmark_review.signal"),
            "detail": t("oc.landmark_review.detail"),
            "category": "regulatory",
        })

    if reg and reg.on_national_register and not reg.in_landmark_district:
        constraints.append({
            "signal": t("oc.nr_review.signal"),
            "detail": t("oc.nr_review.detail"),
            "category": "regulatory",
        })

    if reg and reg.in_aro_zone and dev and dev.max_buildable_sqft:
        # ARO only bites residential projects of 10+ units. Estimate the as-of-right
        # unit capacity (min lot area per unit, else a ~1,000 sf/unit rule of thumb)
        # and skip the flag when the lot plainly can't reach 10 units — otherwise a
        # tiny lot wrongly surfaces ARO as a binding constraint.
        from backend.retrieval.zoning_definitions import min_lot_area_per_unit
        zone_class = ctx.parcel_zoning.zone_class if ctx.parcel_zoning else None
        mla = min_lot_area_per_unit(zone_class)
        if prop and prop.land_sqft and mla:
            est_units = prop.land_sqft / mla
        else:
            est_units = dev.max_buildable_sqft / 1000.0
        if est_units >= 9:  # within rounding of the 10-unit threshold
            constraints.append({
                "signal": t("oc.aro_requirement.signal"),
                "detail": t("oc.aro_requirement.detail"),
                "category": "regulatory",
            })

    if reg and any(o.layer_type == "pedestrian_street" for o in (reg.overlays or [])):
        opportunities.append({
            "signal": t("oc.pedestrian_overlay.signal"),
            "detail": t("oc.pedestrian_overlay.detail"),
            "category": "regulatory",
        })

    if reg and reg.in_ssa:
        constraints.append({
            "signal": t("oc.ssa_levy.signal"),
            "detail": t("oc.ssa_levy.detail", ssa=reg.ssa_name or ""),
            "category": "financial",
        })

    # --- Financial ---
    # "High tax burden" must be judged relative to the CLASS-NORMAL rate: the
    # effective rate scales with the assessment level, so ~5% is ordinary for
    # class-5 commercial (0.25) while it would be alarming for residential
    # (0.10). Normalizing to a residential-equivalent rate keeps the 3.5%
    # threshold meaning "high for what this parcel is" — the absolute test
    # flagged every correctly-computed commercial parcel (2026-07-06 audit).
    if report.effective_tax_rate:
        _level = report.assessment_level or 0.10
        if report.effective_tax_rate * (0.10 / _level) > 0.035:
            constraints.append({
                "signal": t("oc.high_tax.signal", rate=f"{report.effective_tax_rate:.1%}"),
                "detail": t("oc.high_tax.detail"),
                "category": "financial",
            })

    if report.assessment_trend and report.assessment_trend.get("cagr_pct", 0) > 5:
        # Rising assessed value is a reassessment-cycle signal, not realized market
        # appreciation, and it raises the tax burden — frame it as a trend/cost to
        # verify, not an "appreciation opportunity" (see P7).
        opportunities.append({
            "signal": t("oc.assessed_rising.signal", cagr=f"{report.assessment_trend['cagr_pct']:.1f}"),
            "detail": t("oc.assessed_rising.detail", pct=f"{report.assessment_trend['total_change_pct']:.0f}", years=report.assessment_trend['years'], oldest=report.assessment_trend.get('oldest_year'), newest=report.assessment_trend.get('newest_year')),
            "category": "market",
        })

    if comps and comps.sales_volume and comps.sales_volume < 3:
        constraints.append({
            "signal": t("oc.thin_comps.signal", n=comps.sales_volume),
            "detail": t("oc.thin_comps.detail"),
            "category": "market",
        })

    # --- Site condition ---
    if report.address_violations:
        open_v = [v for v in report.address_violations if v.get("violation_status") == "OPEN"]
        if len(open_v) > 10:
            constraints.append({
                "signal": t("oc.open_violations.signal", n=len(open_v)),
                "detail": t("oc.open_violations.detail"),
                "category": "site_condition",
            })
        elif len(open_v) > 0:
            opportunities.append({
                "signal": t("oc.violations_leverage.signal", n=len(open_v)),
                "detail": t("oc.violations_leverage.detail"),
                "category": "site_condition",
            })

    if ctx.address_311 and ctx.address_311.high_risk_flags:
        constraints.append({
            "signal": t("oc.high_risk_311.signal"),
            "detail": t("oc.high_risk_311.detail", flags=", ".join(ctx.address_311.high_risk_flags)),
            "category": "site_condition",
        })

    if report.nearby_development:
        nc = report.nearby_development.new_construction_count or 0
        if nc >= 5:
            opportunities.append({
                "signal": t("oc.active_corridor.signal", n=nc),
                "detail": t("oc.active_corridor.detail"),
                "category": "market",
            })
        elif nc == 0 and (report.nearby_development.demolition_count or 0) == 0:
            constraints.append({
                "signal": t("oc.no_dev_activity.signal"),
                "detail": t("oc.no_dev_activity.detail"),
                "category": "market",
            })

    if report.ownership_signals:
        long_hold = any(s.get("signal") == "Long-Term Hold" for s in report.ownership_signals)
        if long_hold and report.address_violations:
            open_count = len([v for v in report.address_violations if v.get("violation_status") == "OPEN"])
            if open_count > 5:
                opportunities.append({
                    "signal": t("oc.long_held.signal"),
                    "detail": t("oc.long_held.detail", n=open_count),
                    "category": "site_condition",
                })

    # --- Environmental ---
    if reg and reg.in_special_flood_hazard:
        constraints.append({
            "signal": t("oc.sfha.signal", zone=reg.flood_zone),
            "detail": t("oc.sfha.detail"),
            "category": "environmental",
        })

    if reg and reg.brownfield_sites and inc and inc.in_tif_district:
        opportunities.append({
            "signal": t("oc.tif_brownfield.signal"),
            "detail": t("oc.tif_brownfield.detail", n=len(reg.brownfield_sites)),
            "category": "environmental",
        })

    # Cap at 4+4, prioritizing by category order
    _CAT_PRIORITY = ["incentive", "zoning", "regulatory", "market", "financial", "site_condition", "environmental"]
    opportunities.sort(key=lambda x: _CAT_PRIORITY.index(x["category"]) if x["category"] in _CAT_PRIORITY else 99)
    constraints.sort(key=lambda x: _CAT_PRIORITY.index(x["category"]) if x["category"] in _CAT_PRIORITY else 99)

    return opportunities[:4], constraints[:4]


def _resolve_market_value_and_tax(
    prop,
) -> tuple[float | None, float | None, float | None]:
    """Derive (effective_tax_rate, market_value, assessment_level) for the
    property, with an annual-tax fallback (Q6).

    market_value and effective_tax_rate are surfaced together with assessed
    value in the template so a reader can't misread the effective rate — which
    is computed against *market* value (assessed ÷ the class's Cook County
    assessment level: 10% residential, 25% commercial, …) — as if it applied
    to the much-smaller assessed value.

    When the ptaxsim bill is missing, annual tax is estimated from the
    documented effective rate (`report_fallback_tax_rate`) so the tax row isn't
    all-or-nothing; that path sets `prop.tax_estimate_is_fallback` and leaves
    the effective rate None (recomputing it would circularly echo the assumed
    rate). Mutates `prop` (estimated_annual_tax / total_assessed_value /
    tax_estimate_is_fallback) for downstream rendering.
    """
    if not prop or prop.tax_exempt:
        return None, None, None
    assessed = prop.total_assessed_value
    annual_tax = prop.estimated_annual_tax
    # Fallback: use most recent assessment total if the direct value is missing.
    if not assessed and prop.assessment_history:
        for ah in prop.assessment_history:
            if ah.total and ah.total > 0:
                assessed = ah.total
                break
    if not (assessed and assessed > 0):
        return None, None, None
    # Class-aware level (0.10 residential / 0.25 commercial / …); the old
    # hardcoded 0.10 overstated commercial market value 2.5×. Falls back to
    # 0.10 only when the class is entirely unknown.
    level = (
        getattr(prop, "assessment_level", None)
        or assessment_level_for_class(getattr(prop, "bldg_class", None))
        or 0.10
    )
    market_value = round(assessed / level)
    # Keep the displayed assessed value consistent with market value when it was
    # only recoverable from assessment history.
    if not prop.total_assessed_value:
        prop.total_assessed_value = assessed
    if annual_tax and annual_tax > 0:
        # Prefer the summary's rate: it pairs the PTAXSIM bill with the bill
        # year's OWN assessed value (same-year fact). Recomputing against the
        # newest AV mixes years and understates the rate after a reassessment.
        rate = getattr(prop, "effective_tax_rate", None)
        if not rate:
            rate = round(annual_tax / market_value, 4)
        return rate, market_value, level
    # `report_fallback_tax_rate` documents the typical RESIDENTIAL (level 0.10)
    # effective rate. The composite tax rate applies to assessed value, so the
    # effective-on-market rate scales linearly with the class's assessment
    # level — a class-5 (0.25) parcel pays ~2.5× the residential rate. The old
    # flat multiply understated commercial fallback bills by the same factor.
    prop.estimated_annual_tax = round(
        market_value * get_settings().report_fallback_tax_rate * (level / 0.10)
    )
    prop.tax_estimate_is_fallback = True
    return None, market_value, level


def _compute_land_value_range(report: "ReportData") -> dict | None:
    """Compute estimated land value range from comparable VACANT-LAND sales.

    Only confirmed land sales (``sale_type == "LAND"`` — building sqft known
    to be zero) qualify: an improved comp's sale price divided by its land
    area bakes the building's value into the numerator, so a range built from
    it systematically overstates land value (2026-07-06 audit). When fewer
    than 3 vacant-land comps exist we return None and the decision box falls
    back to the honest observed-sales line rather than a fabricated
    "land value".
    """
    comps = report.comparables
    prop = report.context.property
    if not comps or not comps.sales:
        return None
    if not prop or not prop.land_sqft or prop.land_sqft <= 0:
        return None

    prices_per_sqft = [
        s.price_per_land_sqft
        for s in comps.sales
        if s.sale_type == "LAND" and s.price_per_land_sqft and s.price_per_land_sqft > 0
    ]
    if len(prices_per_sqft) < 3:
        return None

    prices_per_sqft.sort()
    n = len(prices_per_sqft)
    p25_idx = max(0, int(n * 0.25))
    p75_idx = min(n - 1, int(n * 0.75))
    low_per_sqft = round(prices_per_sqft[p25_idx], 0)
    high_per_sqft = round(prices_per_sqft[p75_idx], 0)
    low = round(low_per_sqft * prop.land_sqft)
    high = round(high_per_sqft * prop.land_sqft)

    return {
        "low": low,
        "high": high,
        "low_per_sqft": low_per_sqft,
        "high_per_sqft": high_per_sqft,
        "sample_size": len(prices_per_sqft),
    }


def _compute_comp_valuation(report: "ReportData") -> dict | None:
    """Synthesize the comparable-sales set into a subject-lot valuation read (P2).

    The reliable anchor is the median comparable *sale price* (always available
    when comps exist). When ≥3 comps carry a land area we also surface a
    lot-normalized land-value range and a $/buildable-sf figure tied to the
    subject's max buildable. In dense, condo-dominated markets the assessor
    characteristics file rarely reports land area, so the land-normalized layer
    is frequently unavailable — we flag that honestly rather than fabricate it.
    """
    comps = report.comparables
    if not comps or not comps.sales or not comps.sales_volume:
        return None

    dev = report.development_potential
    out: dict[str, Any] = {
        "median_sale_price": comps.median_sale_price,
        "median_price_per_bldg_sqft": comps.median_price_per_bldg_sqft,
        "price_range_min": comps.price_range_min,
        "price_range_max": comps.price_range_max,
        "sample_size": comps.sales_volume,
        "comp_basis": comps.comp_basis,
        "data_limited": True,
    }

    land = report.estimated_land_value
    if land:
        out["data_limited"] = False
        out["land_value_low"] = land["low"]
        out["land_value_high"] = land["high"]
        out["land_per_sqft_low"] = land["low_per_sqft"]
        out["land_per_sqft_high"] = land["high_per_sqft"]
        out["land_sample_size"] = land["sample_size"]
        # P2: spread the implied land value across the max buildable envelope to
        # express a land cost per buildable sq ft — the figure a developer uses
        # to test a deal against construction cost + target return.
        if dev and dev.max_buildable_sqft:
            out["per_buildable_low"] = round(land["low"] / dev.max_buildable_sqft, 2)
            out["per_buildable_high"] = round(land["high"] / dev.max_buildable_sqft, 2)

    return out


def _compute_far_utilization(report: "ReportData") -> dict | None:
    """How much of the FAR-allowed floor area the existing structure uses (P1)."""
    prop = report.context.property
    standards = report.zoning_standards
    if not prop or not prop.land_sqft or not standards or standards.far is None:
        return None
    allowed = int(standards.far * prop.land_sqft)
    if allowed <= 0:
        return None
    existing = prop.bldg_sqft or 0
    return {
        "existing_sqft": existing,
        "allowed_sqft": allowed,
        "far": standards.far,
        "utilization_pct": round(existing / allowed * 100),
        "unused_sqft": max(0, allowed - existing),
        "vacant": existing == 0,
    }


def _compute_unit_yield(report: "ReportData") -> dict | None:
    """As-of-right dwelling-unit yield from minimum lot area per unit (P8).

    Uses the binding lot-area-per-unit density control (Table 17-2-0303-A for
    R districts; the dash-number tables in §17-3-0400 / §17-4-0400 for B/C and
    D districts), not FAR, which is the actual as-of-right cap on unit count.
    Returns ``None`` for districts that permit no dwelling units (C3, M, DS)
    and unknown classes so we never fabricate a yield.
    """
    from backend.retrieval.zoning_definitions import min_lot_area_per_unit
    prop = report.context.property
    zoning = report.context.parcel_zoning
    if not prop or not prop.land_sqft or not zoning or not zoning.zone_class:
        return None
    mla = min_lot_area_per_unit(zoning.zone_class)
    if not mla:
        return None
    units = int(prop.land_sqft // mla)
    if units < 1:
        return None
    return {
        "units": units,
        "mla_per_unit": mla,
        "land_sqft": prop.land_sqft,
        "zone_class": zoning.zone_class.strip().upper(),
    }


def _ownership_interpretation(report: "ReportData") -> str | None:
    """Turn raw ownership signals into a deal read — the 'so what' (P5)."""
    sigs = report.ownership_signals
    if not sigs:
        return None
    names = {s.get("signal") for s in sigs}
    clauses: list[str] = []
    if "Long-Term Hold" in names:
        clauses.append(
            "The owner has held for over a decade, so the parcel is likely off-market — "
            "expect to initiate direct outreach with limited competitive tension, but note "
            "the owner faces no acquisition-cost pressure to sell"
        )
    elif "Recent Acquisition" in names:
        clauses.append(
            "The owner acquired recently, so their cost basis is near current market — this "
            "limits room for a price discount and suggests the site may not be actively for sale"
        )
    elif "Ownership Duration" in names:
        clauses.append(
            "The owner has held for several years, so the parcel is likely off-market — expect "
            "direct outreach rather than a listed sale, with the owner's basis set a few years back"
        )
    if "Owner-Occupied (Homeowner Exemption)" in names:
        clauses.append(
            "A homeowner exemption indicates owner occupancy, so any sale hinges on the owner's "
            "own relocation timeline"
        )
    if "Non-Arm's-Length Transfer" in names or "Quit Claim Deed" in names:
        clauses.append(
            "The most recent transfer was non-arm's-length, so the recorded price does not reflect "
            "market value and true ownership may sit behind a trust or LLC — verify the decision-maker "
            "before making an offer"
        )
    if "Rapid Turnover" in names:
        clauses.append(
            "The property has changed hands rapidly, which can signal investor flipping or unresolved "
            "issues — diligence the reason for the quick resale"
        )
    if not clauses:
        return None
    return ". ".join(clauses) + "."


def _build_decision_box(report: "ReportData") -> dict:
    """Page-1 go/no-go box: lot · zone · buildable · value · constraint · timeline (Miss#1)."""
    t = report_i18n.make_translator(report.language)
    tn = report_i18n.make_plural(report.language)
    na = t("db.na")
    sqft = t("common.sqft")
    prop = report.context.property
    zoning = report.context.parcel_zoning
    dev = report.development_potential

    lot = f"{prop.land_sqft:,} {sqft}" if prop and prop.land_sqft else na
    zone = zoning.zone_class if zoning and zoning.zone_class else na
    buildable = f"{dev.max_buildable_sqft:,} {sqft}" if dev and dev.max_buildable_sqft else na

    # Value field. Credibility rule: never imply a subject valuation we can't
    # support. Tax-exempt/institutional parcels get a status read (more decision-
    # relevant than nearby residential sales); a real land-value range wins when
    # available; otherwise we surface *observed nearby sales* — labeled as market
    # context, not a valuation — and drop the word "median" below n=3 where it is
    # statistically meaningless.
    prop_exempt = bool(prop and (prop.tax_exempt or (prop.bldg_class or "").upper().startswith("EX")))
    value = na
    value_label = t("db.value_label_market")
    elv = report.estimated_land_value
    cv = report.comp_valuation
    if prop_exempt:
        value_label = t("db.value_label_tax")
        value = t("db.exempt_value")
    elif elv:
        value_label = t("db.value_label_land")
        value = f"{_fmt_money(elv['low'])}–{_fmt_money(elv['high'])}"
    elif cv and cv.get("sample_size", 0) >= 3 and cv.get("median_sale_price"):
        value_label = t("db.value_label_nearby_median")
        value = f"{_fmt_money(cv['median_sale_price'])} · n={cv['sample_size']}"
    elif cv and cv.get("sample_size", 0) >= 1 and cv.get("price_range_min"):
        n = cv["sample_size"]
        value_label = t("db.value_label_nearby")
        value = f"{_fmt_money(cv['price_range_min'])}–{_fmt_money(cv['price_range_max'])} · {tn('db.sale_count', n, n=n)}"

    # Surface the most *deal-shaping* constraint, not merely the first synthesized
    # one — regulatory / environmental / site issues bind a project harder than a
    # thin-comp-market caveat, so order by how much each gates a go/no-go decision.
    # "No major constraints flagged" (not "None identified") so the absence reads
    # as "our rule set found nothing," not a guarantee the site is unencumbered.
    key_constraint = t("db.key_constraint_none")
    if report.constraints:
        _binding_order = [
            "regulatory", "environmental", "site_condition",
            "zoning", "financial", "incentive", "market",
        ]
        top = min(
            report.constraints,
            key=lambda c: _binding_order.index(c["category"])
            if c.get("category") in _binding_order else 99,
        )
        key_constraint = top["signal"]

    timeline = na
    if report.approval_pathway:
        ap = report.approval_pathway
        timeline = f"{t('pill.' + ap['complexity'].lower()).capitalize()} · {ap['timeline']}"

    return {
        "lot": lot,
        "zone": zone,
        "buildable": buildable,
        "value": value,
        "value_label": value_label,
        "key_constraint": key_constraint,
        "timeline": timeline,
    }


def _compute_approval_pathway(report: "ReportData") -> dict | None:
    """Determine regulatory approval complexity from report data."""
    reg = report.context.regulatory
    if not reg:
        return None

    t = report_i18n.make_translator(report.language)
    standards = report.zoning_standards
    has_special = standards and standards.special_uses
    has_permitted = standards and standards.permitted_uses

    if reg.in_planned_development:
        complexity = "COMPLEX"
        detail = t("ap.pd_detail")
        timeline = t("ap.pd_timeline")
    elif reg.in_landmark_district or reg.in_historic_district:
        complexity = "COMPLEX"
        detail = t("ap.landmark_detail")
        timeline = t("ap.landmark_timeline")
    elif reg.on_national_register:
        complexity = "MODERATE"
        detail = t("ap.nr_detail")
        timeline = t("ap.nr_timeline")
    elif has_special and not has_permitted:
        complexity = "MODERATE"
        detail = t("ap.special_zba_detail")
        timeline = t("ap.special_zba_timeline")
    elif has_special and has_permitted:
        complexity = "MODERATE"
        detail = t("ap.special_some_detail")
        timeline = t("ap.special_some_timeline")
    else:
        complexity = "SIMPLE"
        detail = t("ap.simple_detail")
        timeline = t("ap.simple_timeline")

    modifiers: list[str] = []
    if report.address_violations:
        open_count = len([v for v in report.address_violations if v.get("violation_status") == "OPEN"])
        if open_count > 5:
            modifiers.append(t("ap.mod_violation"))
    if reg.in_special_flood_hazard:
        modifiers.append(t("ap.mod_floodplain"))
    if reg.in_aro_zone:
        modifiers.append(t("ap.mod_aro"))
    if any(o.layer_type == "pedestrian_street" for o in (reg.overlays or [])):
        modifiers.append(t("ap.mod_pedestrian"))

    return {
        "complexity": complexity,
        "detail": detail,
        "timeline": timeline,
        "modifiers": modifiers,
    }


def _fmt_money(amount: float) -> str:
    """Format a dollar amount with a consistent magnitude suffix ($K below $1M, $M above)."""
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    return f"${amount / 1_000:.0f}K"


def _compute_development_trend(report: "ReportData") -> dict | None:
    """Synthesize nearby development data into a narrative summary."""
    nd = report.nearby_development
    if not nd:
        return None

    # Radius label derived from the actual construction-search config (0.5mi),
    # not a stale hardcoded "0.25mi" that contradicts the section header.
    radius_mi = round(get_settings().nearby_construction_radius_deg * MI_PER_DEG_LAT, 2)
    radius_label = f"{radius_mi:g}mi"

    tn = report_i18n.make_plural(report.language)
    nc = nd.new_construction_count or 0
    demo = nd.demolition_count or 0
    projects = nd.recent_projects or []

    if nc == 0 and demo == 0:
        return {
            "narrative": tn("dt.quiet", len(projects), n=len(projects), radius=radius_label),
            "intensity": "quiet",
        }

    # True area/window aggregate (new-construction permits only) — not a sum
    # over the capped recent_projects sample with demolition costs mixed in.
    total_investment = nd.new_construction_cost or 0

    if nc > 0 and total_investment > 0:
        avg_cost = total_investment / max(nc, 1)
        narrative = tn(
            "dt.active", nc, nc=nc, total=_fmt_money(total_investment),
            radius=radius_label, avg=_fmt_money(avg_cost),
        )
        if demo > 0:
            narrative += tn("dt.active_demo", demo, demo=demo)
        intensity = "active" if nc >= 3 else "moderate"
    elif demo > nc:
        narrative = tn("dt.teardown", demo, demo=demo, nc=nc)
        intensity = "transitional"
    else:
        narrative = tn("dt.moderate", nc + demo, n=nc + demo, radius=radius_label)
        intensity = "moderate"

    return {
        "narrative": narrative,
        "intensity": intensity,
        "total_investment": total_investment,
        "new_construction_count": nc,
        "demolition_count": demo,
    }


def _build_incentive_stacking_narrative(report: "ReportData") -> str | None:
    """Generate a paragraph explaining how multiple incentive programs combine."""
    inc = report.context.incentives
    if not inc:
        return None

    flags = []
    if inc.in_tif_district:
        flags.append("TIF")
    if inc.in_opportunity_zone:
        flags.append("OZ")
    if inc.in_enterprise_zone:
        flags.append("EZ")
    if inc.in_qct:
        flags.append("QCT")
    if inc.in_nmtc:
        flags.append("NMTC")

    if len(flags) < 2:
        return None

    t = report_i18n.make_translator(report.language)
    key = "+".join(sorted(flags))
    # Map the sorted-flag combo to its catalog key (deterministic, no LLM).
    combo_keys = {
        "OZ+TIF": "isn.oz_tif",
        "EZ+TIF": "isn.ez_tif",
        "OZ+QCT": "isn.oz_qct",
        "OZ+QCT+TIF": "isn.oz_qct_tif",
        "NMTC+TIF": "isn.nmtc_tif",
        "EZ+OZ": "isn.ez_oz",
    }
    catalog_key = combo_keys.get(key)
    if catalog_key:
        return t(catalog_key)

    return t("isn.fallback", count=len(flags), flags=", ".join(flags))


def _build_envelope_summary(report: "ReportData") -> str | None:
    """Assemble development parameters into one readable block."""
    standards = report.zoning_standards
    dev = report.development_potential
    prop = report.context.property
    zoning = report.context.parcel_zoning

    if not standards or not prop or not prop.land_sqft:
        return None

    t = report_i18n.make_translator(report.language)
    zone = zoning.zone_class if zoning else t("env.this_district")
    parts = [t("env.lead", land=f"{prop.land_sqft:,}", zone=zone)]

    if dev and dev.max_buildable_sqft:
        parts.append(t("env.allows_buildable", v=f"{dev.max_buildable_sqft:,}"))
    elif standards.far is not None:
        parts.append(t("env.permits_far", far=standards.far))

    if standards.max_stories and standards.max_height_ft:
        parts.append(t("env.across_stories_height", stories=standards.max_stories, height=standards.max_height_ft))
    elif standards.max_stories:
        parts.append(t("env.across_stories", stories=standards.max_stories))
    elif standards.max_height_ft:
        parts.append(t("env.up_to_height", height=standards.max_height_ft))

    parts.append(".")

    if standards.lot_coverage_pct and prop.land_sqft:
        footprint = int(standards.lot_coverage_pct * prop.land_sqft)
        parts.append(t("env.footprint", v=f"{footprint:,}", pct=int(standards.lot_coverage_pct * 100)))

    if standards.permitted_uses:
        top_uses = standards.permitted_uses[:3]
        parts.append(t("env.permitted_uses", uses=", ".join(top_uses)))

    if standards.parking_residential:
        parts.append(t("env.parking", parking=standards.parking_residential))

    return "".join(parts)


def _apply_mock_overrides(report_data: "ReportData") -> "ReportData":
    """Inject realistic test data for visual QA of all v2 sections."""
    from backend.models import (
        AppealRecord, AppealsSummary, AssessmentRecord, ComparableSale,
        ComparablesSummary, DevelopmentPotential, NearbyDevelopment,
        SaleRecord, TaxExemption, TaxLineItem, ZoningStandards,
    )

    # Force zoning extraction with high confidence
    report_data.zoning_standards = ZoningStandards(
        far=2.2,
        max_height_ft=50,
        max_stories=4,
        lot_coverage_pct=0.75,
        min_lot_area_sqft=2500,
        front_setback_ft=10,
        side_setback_ft=5,
        rear_setback_ft=30,
        parking_residential="1 per unit",
        parking_commercial="1 per 500 sq ft GFA",
        permitted_uses=["Retail Sales", "Restaurant", "Office", "Personal Service", "Residential above ground floor"],
        special_uses=["Tavern", "Drive-Through Facility", "Gas Station"],
        notes=["Ground floor transparency minimum 60%", "TOD area may reduce parking requirement"],
        extraction_confidence="high",
    )

    # Force development potential with surplus
    land_sqft = report_data.context.property.land_sqft if report_data.context.property else 5000
    bldg_sqft = report_data.context.property.bldg_sqft if report_data.context.property else 3200
    if not land_sqft:
        land_sqft = 5000
    if not bldg_sqft:
        bldg_sqft = 3200
    report_data.development_potential = DevelopmentPotential(
        max_buildable_sqft=int(2.2 * land_sqft),
        max_lot_coverage_sqft=int(0.75 * land_sqft),
        development_surplus_sqft=int(2.2 * land_sqft) - bldg_sqft,
    )

    # Force effective tax rate + ensure property has tax/assessment for display
    report_data.effective_tax_rate = 0.0218
    if report_data.context.property:
        if not report_data.context.property.estimated_annual_tax:
            report_data.context.property.estimated_annual_tax = 8720
        if not report_data.context.property.total_assessed_value:
            report_data.context.property.total_assessed_value = 40000
        mock_level = (
            assessment_level_for_class(report_data.context.property.bldg_class)
            or 0.10
        )
        report_data.assessment_level = mock_level
        report_data.market_value = round(
            report_data.context.property.total_assessed_value / mock_level
        )

    # Force comparable sales
    report_data.comparables = ComparablesSummary(
        median_sale_price=425000.0,
        median_price_per_land_sqft=142.0,
        median_price_per_bldg_sqft=195.0,
        price_range_min=275000.0,
        price_range_max=680000.0,
        sales_volume=7,
        sales=[
            ComparableSale(pin="14-30-316-001", sale_date="2025-11-14", sale_price=520000, class_code="212", land_sqft=3125, bldg_sqft=2400, price_per_land_sqft=166.4, price_per_bldg_sqft=216.7, deed_type="WARRANTY", distance_mi=0.08, lat=41.9280, lon=-87.6430),
            ComparableSale(pin="14-30-314-022", sale_date="2025-08-22", sale_price=450000, class_code="211", land_sqft=2750, bldg_sqft=1850, price_per_land_sqft=163.6, price_per_bldg_sqft=243.2, deed_type="WARRANTY", distance_mi=0.12, lat=41.9295, lon=-87.6455),
            ComparableSale(pin="14-30-318-015", sale_date="2025-06-03", sale_price=425000, class_code="212", land_sqft=3000, bldg_sqft=2200, price_per_land_sqft=141.7, price_per_bldg_sqft=193.2, deed_type="TRUSTEE", distance_mi=0.15, lat=41.9260, lon=-87.6420),
            ComparableSale(pin="14-30-320-009", sale_date="2025-03-18", sale_price=385000, class_code="211", land_sqft=2800, bldg_sqft=2100, price_per_land_sqft=137.5, price_per_bldg_sqft=183.3, deed_type="WARRANTY", distance_mi=0.18, lat=41.9310, lon=-87.6400),
            ComparableSale(pin="14-30-312-041", sale_date="2024-12-05", sale_price=680000, class_code="212", land_sqft=4500, bldg_sqft=3600, price_per_land_sqft=151.1, price_per_bldg_sqft=188.9, deed_type="WARRANTY", distance_mi=0.21, lat=41.9245, lon=-87.6445),
            ComparableSale(pin="14-30-322-007", sale_date="2024-09-11", sale_price=310000, class_code="211", land_sqft=2500, bldg_sqft=1600, price_per_land_sqft=124.0, price_per_bldg_sqft=193.8, deed_type="WARRANTY", distance_mi=0.22, lat=41.9320, lon=-87.6430),
            ComparableSale(pin="14-30-310-033", sale_date="2024-06-27", sale_price=275000, class_code="211", land_sqft=2400, bldg_sqft=1500, price_per_land_sqft=114.6, price_per_bldg_sqft=183.3, deed_type="TRUSTEE", distance_mi=0.24, lat=41.9250, lon=-87.6460),
        ],
    )

    # Force address-specific permits
    report_data.address_permits = [
        {"permit_": "100654321", "permit_type": "PERMIT - RENOVATION/ALTERATION", "work_description": "INTERIOR RENOVATION - COMMERCIAL SPACE BUILDOUT FOR RESTAURANT", "issue_date": "2025-09-14", "reported_cost": "185000", "contact_1_name": "ABC CONSTRUCTION LLC"},
        {"permit_": "100654322", "permit_type": "PERMIT - SIGNS", "work_description": "INSTALL ILLUMINATED WALL SIGN 4x8", "issue_date": "2025-06-02", "reported_cost": "8500", "contact_1_name": "CHICAGO SIGN CO"},
        {"permit_": "100654323", "permit_type": "PERMIT - EASY PERMIT PROCESS", "work_description": "ELECTRICAL - UPGRADE SERVICE TO 400A", "issue_date": "2025-01-18", "reported_cost": "12000", "contact_1_name": "METRO ELECTRIC INC"},
        {"permit_": "100654324", "permit_type": "PERMIT - RENOVATION/ALTERATION", "work_description": "TUCKPOINTING AND MASONRY REPAIR - REAR WALL", "issue_date": "2024-08-22", "reported_cost": "45000", "contact_1_name": "LAKESIDE MASONRY"},
        {"permit_": "100654325", "permit_type": "PERMIT - EASY PERMIT PROCESS", "work_description": "PLUMBING - REPLACE WATER HEATER", "issue_date": "2024-03-11", "reported_cost": "3200", "contact_1_name": "AAA PLUMBING SERVICES"},
    ]

    # Force address-specific violations
    report_data.address_violations = [
        {"violation_date": "2025-04-15", "violation_status": "OPEN", "inspection_number": "14823456", "violation_description": "FAILURE TO MAINTAIN EXTERIOR WALLS - DETERIORATED MASONRY MORTAR JOINTS ON NORTH ELEVATION"},
        {"violation_date": "2024-11-03", "violation_status": "COMPLIED", "inspection_number": "14712345", "violation_description": "FAILED TO MAINTAIN REQUIRED EXIT SIGN ILLUMINATION IN REAR STAIRWELL"},
        {"violation_date": "2024-06-20", "violation_status": "COMPLIED", "inspection_number": "14601234", "violation_description": "FAILURE TO MAINTAIN ALLEY AND REAR YARD FREE OF DEBRIS AND REFUSE"},
    ]

    # Force nearby development (with lat/lon for map generation)
    mock_lat = report_data.lat or 41.9270
    mock_lon = report_data.lon or -87.6980
    report_data.nearby_development = NearbyDevelopment(
        new_construction_count=4,
        demolition_count=2,
        recent_projects=[
            {"permit_type": "PERMIT - NEW CONSTRUCTION", "latitude": str(mock_lat + 0.001), "longitude": str(mock_lon + 0.001), "work_description": "Erect new 3-story mixed-use building", "issue_date": "2025-11-15", "reported_cost": "450000", "street_number": "2410", "street_direction": "N", "street_name": "MILWAUKEE AVE", "distance_mi": 0.07, "formatted_address": "2410 N MILWAUKEE AVE"},
            {"permit_type": "PERMIT - NEW CONSTRUCTION", "latitude": str(mock_lat - 0.001), "longitude": str(mock_lon + 0.002), "work_description": "Erect new single-family residence", "issue_date": "2025-09-22", "reported_cost": "280000", "street_number": "2356", "street_direction": "N", "street_name": "KEDZIE AVE", "distance_mi": 0.12, "formatted_address": "2356 N KEDZIE AVE"},
            {"permit_type": "PERMIT - NEW CONSTRUCTION", "latitude": str(mock_lat + 0.002), "longitude": str(mock_lon - 0.001), "work_description": "Erect new 6-unit residential building", "issue_date": "2025-08-10", "reported_cost": "720000", "street_number": "2430", "street_direction": "N", "street_name": "CALIFORNIA AVE", "distance_mi": 0.15, "formatted_address": "2430 N CALIFORNIA AVE"},
            {"permit_type": "PERMIT - NEW CONSTRUCTION", "latitude": str(mock_lat - 0.002), "longitude": str(mock_lon - 0.002), "work_description": "Erect new commercial building", "issue_date": "2025-06-05", "reported_cost": "950000", "street_number": "2501", "street_direction": "N", "street_name": "MILWAUKEE AVE", "distance_mi": 0.20, "formatted_address": "2501 N MILWAUKEE AVE"},
            {"permit_type": "PERMIT - WRECKING/DEMOLITION", "latitude": str(mock_lat + 0.0015), "longitude": str(mock_lon - 0.0015), "work_description": "Wreck existing 2-story frame building", "issue_date": "2025-10-01", "reported_cost": "35000", "street_number": "2418", "street_direction": "N", "street_name": "SACRAMENTO AVE", "distance_mi": 0.11, "formatted_address": "2418 N SACRAMENTO AVE"},
            {"permit_type": "PERMIT - WRECKING/DEMOLITION", "latitude": str(mock_lat - 0.0015), "longitude": str(mock_lon + 0.0005), "work_description": "Wreck existing garage structure", "issue_date": "2025-07-18", "reported_cost": "15000", "street_number": "2380", "street_direction": "N", "street_name": "MILWAUKEE AVE", "distance_mi": 0.13, "formatted_address": "2380 N MILWAUKEE AVE"},
        ],
    )

    # Force building characteristics + history (development_feasibility workflow skips history)
    if report_data.context.property:
        report_data.context.property.exterior_wall = report_data.context.property.exterior_wall or "Masonry"
        report_data.context.property.roof_type = report_data.context.property.roof_type or "Shingle/Asphalt"
        report_data.context.property.basement = report_data.context.property.basement or "Full"
        report_data.context.property.garage_size = report_data.context.property.garage_size or "1 Car"
        report_data.context.property.air_conditioning = report_data.context.property.air_conditioning or "Central"
        if not report_data.context.property.year_built and report_data.context.property.bldg_age:
            from datetime import date
            report_data.context.property.year_built = date.today().year - report_data.context.property.bldg_age

        if not report_data.context.property.assessment_history:
            report_data.context.property.assessment_history = [
                AssessmentRecord(year=2025, land=12000, building=27900, total=39900),
                AssessmentRecord(year=2024, land=11500, building=26000, total=37500),
                AssessmentRecord(year=2023, land=10800, building=24200, total=35000),
                AssessmentRecord(year=2022, land=10000, building=22000, total=32000),
                AssessmentRecord(year=2021, land=9500, building=18500, total=28000),
            ]
            report_data.context.property.total_assessed_value = 39900

        if not report_data.context.property.sales_history:
            report_data.context.property.sales_history = [
                SaleRecord(date="2014-03-22", price=285000, deed_type="WARRANTY"),
                SaleRecord(date="2005-09-15", price=192000, deed_type="WARRANTY"),
                SaleRecord(date="1998-06-01", price=125000, deed_type="TRUSTEE"),
            ]

        if not report_data.context.property.appeals:
            report_data.context.property.appeals = AppealsSummary(
                records=[
                    AppealRecord(year=2024, stage="board_of_review", before_total=39900,
                                 after_total=33200, result="Decrease", reduction_pct=16.8,
                                 appeal_type="Over Valuation"),
                    AppealRecord(year=2023, stage="assessor", before_total=37500,
                                 after_total=37500, result="no change"),
                ],
                nearby_window_years=[2022, 2023, 2024],
                nearby_appeal_count=107,
                nearby_reduced_count=38,
                nearby_median_reduction_pct=16.9,
            )

        if not report_data.context.property.tax_exemptions:
            report_data.context.property.tax_exemptions = [
                TaxExemption(kind="Homeowner", eav_reduction=10000),
            ]

        if not report_data.context.property.tax_breakdown:
            report_data.context.property.tax_breakdown = [
                TaxLineItem(agency="CITY OF CHICAGO", rate=0.01245, amount=4215.60),
                TaxLineItem(agency="BOARD OF EDUCATION", rate=0.00980, amount=3316.20),
                TaxLineItem(agency="COOK COUNTY FOREST PRESERVE", rate=0.00162, amount=548.44),
                TaxLineItem(agency="METRO WATER RECLAMATION", rate=0.00410, amount=1387.86),
                TaxLineItem(agency="CHICAGO PARK DISTRICT", rate=0.00315, amount=1066.14),
                TaxLineItem(agency="CITY COLLEGES", rate=0.00205, amount=693.90),
                TaxLineItem(agency="COOK COUNTY", rate=0.00175, amount=592.34),
                TaxLineItem(agency="COOK COUNTY HEALTH FACILITIES", rate=0.00098, amount=331.63),
            ]

    # Force assessment trend
    report_data.assessment_trend = {
        "total_change_pct": 42.5,
        "cagr_pct": 7.3,
        "years": 5,
        "oldest_year": 2020,
        "newest_year": 2025,
        "oldest_total": 28000,
        "newest_total": 39900,
        "direction": "increasing",
    }

    # Force ownership signals
    report_data.ownership_signals = [
        {"signal": "Long-Term Hold", "detail": "Last sale 12 years ago (2014-03-22)", "category": "ownership_duration"},
        {"signal": "Owner-Occupied (Homeowner Exemption)", "detail": "Homeowner exemption found in tax breakdown", "category": "occupancy"},
    ]

    # Force parcel dimensions (mock rectangular lot)
    report_data.parcel_dimensions = {
        "area_sqft": 3125,
        "perimeter_ft": 250.0,
        "frontage_ft": 25.0,
        "depth_ft": 125.0,
        "edge_count": 4,
        "edges": [
            {"length_ft": 125.0, "bearing": 0.0},
            {"length_ft": 25.0, "bearing": 90.0},
            {"length_ft": 125.0, "bearing": 180.0},
            {"length_ft": 25.0, "bearing": 270.0},
        ],
    }

    # Force adjacent zoning
    report_data.adjacent_zoning = {"N": "B3-2", "S": "RS-3", "E": "B3-2", "W": "RT-4"}

    # NOTE: parcel_geometry is NOT mocked — fabricated coordinates produce a
    # misleading lot map. The parcel map only renders with real GIS geometry.
    # Mock parcel_dimensions (below) still populate the dimensions grid.

    # Generate comps chart for mock data
    try:
        report_data.comps_chart_b64 = _generate_comps_chart(report_data.comparables)
    except Exception:
        pass

    # Envelope map for mock data
    if report_data.context.property and report_data.context.property.parcel_geometry and report_data.zoning_standards:
        try:
            report_data.envelope_map_b64, report_data.buildable_footprint_sqft = _generate_envelope_map(
                report_data.lat, report_data.lon,
                report_data.context.property.parcel_geometry,
                report_data.zoning_standards,
                report_data.parcel_dimensions,
            )
        except Exception:
            log.warning("Failed to generate mock envelope map", exc_info=True)

    # V5 synthesis on mock data
    report_data.opportunities, report_data.constraints = _synthesize_opportunities_constraints(report_data)
    report_data.estimated_land_value = _compute_land_value_range(report_data)
    report_data.approval_pathway = _compute_approval_pathway(report_data)
    report_data.development_trend = _compute_development_trend(report_data)
    report_data.incentive_stacking_narrative = _build_incentive_stacking_narrative(report_data)
    report_data.envelope_summary = _build_envelope_summary(report_data)

    # Phase 3 decision-quality synthesis on mock data
    report_data.far_utilization = _compute_far_utilization(report_data)
    report_data.unit_yield = _compute_unit_yield(report_data)
    report_data.comp_valuation = _compute_comp_valuation(report_data)
    report_data.ownership_interpretation = _ownership_interpretation(report_data)
    report_data.decision_box = _build_decision_box(report_data)

    # Clear partial failures since mock data is complete
    report_data.partial_failures = []

    return report_data
