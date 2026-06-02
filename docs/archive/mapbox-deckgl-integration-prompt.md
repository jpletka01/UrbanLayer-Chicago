# Map Integration Prompt — Chicago City Intelligence
## Mapbox GL JS + Deck.gl Layer

Use this prompt with Claude Code inside the `chicago-rag/` project.

---

## Objective

Extend the Chicago City Intelligence RAG app with an interactive map panel built on **Mapbox GL JS** and **Deck.gl**. The map should visualize the same city data that the chat interface queries — crimes, 311 service requests, building permits, and zoning districts — and update reactively when the user submits a query. The address pin and the chat panel should stay in sync.

---

## Context

This project already has:
- A FastAPI `/chat` endpoint that returns a structured JSON response
- React frontend with a working chat UI (`ChatInterface.jsx`, `MessageBubble.jsx`)
- Socrata API wrappers for crime (`crime.py`), 311 (`three11.py`), and buildings (`buildings.py`)
- A context assembler (`assembler.py`) that shapes structured results including lat/lng fields

Do not change any existing backend logic. The map is purely a frontend addition, with one new backend endpoint for raw geo data.

---

## What to Build

### 1. New Backend Endpoint — `/api/map-data`

Add a new FastAPI route in `main.py`. This endpoint accepts the same location parameters the chat router resolves, and returns raw GeoJSON-ready arrays for the map layers.

**Request shape:**
```json
{
  "community_area": 24,
  "time_range_days": 90
}
```

**Response shape:**
```json
{
  "crimes": [
    {
      "latitude": 41.925,
      "longitude": -87.712,
      "primary_type": "THEFT",
      "date": "2025-05-01T14:22:00",
      "description": "FROM BUILDING",
      "arrest": false
    }
  ],
  "requests_311": [
    {
      "latitude": 41.923,
      "longitude": -87.710,
      "sr_type": "Pothole in Street",
      "status": "Open",
      "created_date": "2025-04-15T09:00:00",
      "owner_department": "Streets & Sanitation"
    }
  ],
  "building_permits": [
    {
      "latitude": 41.924,
      "longitude": -87.711,
      "permit_type": "PERMIT - NEW CONSTRUCTION",
      "work_description": "ERECT NEW 3-FLAT",
      "estimated_cost": 450000,
      "issue_date": "2025-03-10"
    }
  ],
  "zoning": {
    "type": "FeatureCollection",
    "features": []
  },
  "queried_address": {
    "latitude": 41.9252,
    "longitude": -87.7118,
    "label": "2400 N Milwaukee Ave"
  }
}
```

Use the existing async Socrata wrappers with `asyncio.gather()`. For crimes and 311, reuse the patterns in `crime.py` and `three11.py` but return raw rows with lat/lng instead of aggregated counts. Cap results:
- Crimes: `$limit=200`, order by `date DESC`
- 311: `$limit=150`, filter `status != 'Open - Dup'`, order by `created_date DESC`
- Building permits: `$limit=100`, order by `issue_date DESC`

For zoning, query the Socrata dataset `p8va-airx` using the `.geojson` endpoint format, which returns a properly structured GeoJSON FeatureCollection directly:

```
GET https://data.cityofchicago.org/resource/p8va-airx.geojson
  ?$where=community_area='{ca}'
```

Pass this response through to the frontend as-is — no reshaping needed, it drops straight into deck.gl's `GeoJsonLayer`.

**Coordinate system note:** The Socrata `.geojson` endpoint serves coordinates in WGS84 (EPSG 4326), which is standard lat/lng and what Mapbox and deck.gl expect. However, if zoning data is ever sourced from a shapefile download (e.g. from the city's GIS portal directly), it may be projected in Illinois State Plane (ESRI 3435) instead. Those coordinates will be in feet, not degrees, and will render in the wrong location entirely. If you see zoning polygons appearing far outside Chicago, reprojection is the cause — use the `proj4` library to convert to WGS84 before passing to the frontend. The Socrata API endpoint does not have this problem.

If zoning returns no results or errors, return an empty FeatureCollection — do not fail the whole request.

Skip rows with null latitude or longitude before returning.

---

### 2. New Frontend Components

#### `MapPanel.jsx`

A full-height map panel rendered alongside (or below, on mobile) the chat interface. Initialize a Mapbox GL JS map with the Chicago Style Streets basemap. Layer deck.gl on top using `@deck.gl/mapbox` or the standalone `Deck` class with `interleaved: true`.

**Map initialization:**
```javascript
import mapboxgl from 'mapbox-gl';
import { Deck } from '@deck.gl/core';

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN;

const map = new mapboxgl.Map({
  container: mapContainerRef.current,
  style: 'mapbox://styles/mapbox/streets-v12',
  center: [-87.6298, 41.8781],
  zoom: 12,
});
```

**Deck.gl layers to render (conditionally, based on active toggles):**

| Layer | Deck.gl type | Data source | Visual encoding |
|---|---|---|---|
| Crimes | `ScatterplotLayer` | `mapData.crimes` | Radius = 60m. Color by `primary_type`: THEFT = amber `[239, 159, 39]`, BATTERY/ASSAULT = red `[226, 75, 74]`, NARCOTICS = purple `[127, 119, 221]`, all others = gray `[136, 135, 128]` |
| 311 requests | `IconLayer` | `mapData.requests_311` | Use a custom SVG icon or atlas. Color by `owner_department`: Streets & Sanitation = teal, Buildings = coral, CDOT = blue |
| Building permits | `ScatterplotLayer` | `mapData.building_permits` | Radius scaled by `estimated_cost` (min 40m, max 200m). Color = green `[99, 153, 34]` |
| Zoning | `GeoJsonLayer` | `mapData.zoning` | Fill with 20% opacity color by zoning classification. Stroke weight 1.5px |
| Address pin | `ScatterplotLayer` (single point) | `mapData.queried_address` | Radius 80m, color = blue `[55, 138, 221]`, filled + white stroke |

**Tooltip:** Implement a hover tooltip using deck.gl's `getTooltip` prop. Show relevant fields per layer type:
- Crime: type, description, date, arrest status
- 311: sr_type, status, department, created date
- Permit: permit type, work description, estimated cost, issue date

**Layer visibility toggles:** Render a floating control panel (top-right of the map) with toggle buttons for each layer. Persist toggle state in React `useState`.

#### `MapLegend.jsx`

A compact legend panel anchored to the bottom-left of the map. Show color swatches and labels for whichever layers are currently toggled on. Hide automatically when no layers are active.

---

### 3. State Management — Connecting Chat to Map

When the `/chat` endpoint returns a response that includes a resolved `community_area` and/or `queried_address`, the frontend should:

1. Automatically fire a `GET /api/map-data` request with those parameters
2. Fly the map to the queried address using `map.flyTo({ center, zoom: 14 })`
3. Update deck.gl layers with the new data
4. Show a loading skeleton on the map panel while the request is in flight

The chat and map panels should be siblings in `App.jsx`, sharing state via a `mapContext` object lifted to the top level (or a simple React context). Do not use Redux or Zustand — keep state local.

Suggested shape of shared state:
```javascript
const [mapContext, setMapContext] = useState({
  communityArea: null,
  queriedAddress: null,
  mapData: null,
  loading: false,
});
```

When a new chat message resolves a location, call `setMapContext` with the updated community area and address. The `MapPanel` component subscribes to this and triggers the `/api/map-data` fetch.

---

### 4. Layout

Update `App.jsx` to use a two-column layout on desktop:

```
┌──────────────────────┬────────────────────────┐
│                      │                        │
│   Chat interface     │     Map panel          │
│   (left, 40%)        │     (right, 60%)       │
│                      │                        │
│                      │  [Layer toggles]       │
│                      │                        │
│                      │  [Legend]              │
└──────────────────────┴────────────────────────┘
```

On mobile (< 768px), stack vertically: chat on top, map below at a fixed height of 360px.

Use CSS Grid:
```css
.app-layout {
  display: grid;
  grid-template-columns: 2fr 3fr;
  height: 100vh;
  overflow: hidden;
}

@media (max-width: 768px) {
  .app-layout {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr 360px;
  }
}
```

---

### 5. Environment Variables

Add to `.env.example`:
```
VITE_MAPBOX_TOKEN=your_mapbox_public_token_here
```

The Mapbox token is a public token (starts with `pk.`). It is safe to include in frontend code — it is not a secret. Mapbox tokens are scoped and rate-limited by domain in the Mapbox dashboard.

---

### 6. Dependencies to Install

**Frontend:**
```bash
npm install mapbox-gl @deck.gl/core @deck.gl/layers @deck.gl/mapbox @deck.gl/geo-layers
```

**No new backend dependencies required** — the `/api/map-data` endpoint reuses existing `aiohttp` Socrata wrappers.

---

## Constraints

- Do not modify `router.py`, `synthesizer.py`, `assembler.py`, or any existing retrieval modules
- Do not add map rendering to the backend — all visualization logic lives in the React frontend
- The map must be functional even when no chat query has been submitted yet (show Chicago centered, no data layers, no error state)
- Handle the case where `/api/map-data` returns empty arrays — layers should render with zero points rather than throwing
- Zoning layer is optional/bonus — if implementing, add it last and gate it behind a feature flag (`VITE_ENABLE_ZONING_LAYER=true`) so it doesn't block the rest of the map work

---

## Build Order for This Feature

1. Add `/api/map-data` endpoint to `main.py` and test it independently with a hardcoded community area (e.g. 24 = West Town) — confirm real lat/lng data returns
2. Install frontend dependencies and confirm Mapbox map renders with just the basemap
3. Add deck.gl `ScatterplotLayer` for crimes only — confirm points appear on the map
4. Add 311 and permit layers
5. Implement the address pin layer
6. Wire chat → map state sync in `App.jsx`
7. Add layer toggle controls and legend
8. Add hover tooltips
9. Add zoning `GeoJsonLayer` last (optional)
