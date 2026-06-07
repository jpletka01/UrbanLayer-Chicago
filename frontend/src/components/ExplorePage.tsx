import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { ScatterplotLayer } from "@deck.gl/layers";
import { useAuthContext } from "../contexts/AuthContext";
import { useMapboxOverlay } from "../lib/useMapboxOverlay";
import {
  fetchExploreParcels,
  fetchExploreMap,
  type ExploreParcel,
  type ExploreResponse,
} from "../lib/api";
import UpgradePrompt from "./UpgradePrompt";

const COMMUNITY_AREAS: Record<number, string> = {
  1: "Rogers Park", 2: "West Ridge", 3: "Uptown", 4: "Lincoln Square",
  5: "North Center", 6: "Lake View", 7: "Lincoln Park", 8: "Near North Side",
  9: "Edison Park", 10: "Norwood Park", 11: "Jefferson Park", 12: "Forest Glen",
  13: "North Park", 14: "Albany Park", 15: "Portage Park", 16: "Irving Park",
  17: "Dunning", 18: "Montclare", 19: "Belmont Cragin", 20: "Hermosa",
  21: "Avondale", 22: "Logan Square", 23: "Humboldt Park", 24: "West Town",
  25: "Austin", 26: "West Garfield Park", 27: "East Garfield Park",
  28: "Near West Side", 29: "North Lawndale", 30: "South Lawndale",
  31: "Lower West Side", 32: "Loop", 33: "Near South Side", 34: "Armour Square",
  35: "Douglas", 36: "Oakland", 37: "Fuller Park", 38: "Grand Boulevard",
  39: "Kenwood", 40: "Washington Park", 41: "Hyde Park", 42: "Woodlawn",
  43: "South Shore", 44: "Chatham", 45: "Avalon Park", 46: "South Chicago",
  47: "Burnside", 48: "Calumet Heights", 49: "Roseland", 50: "Pullman",
  51: "South Deering", 52: "East Side", 53: "West Pullman", 54: "Riverdale",
  55: "Hegewisch", 56: "Garfield Ridge", 57: "Archer Heights",
  58: "Brighton Park", 59: "McKinley Park", 60: "Bridgeport",
  61: "New City", 62: "West Elsdon", 63: "Gage Park", 64: "Clearing",
  65: "West Lawn", 66: "Chicago Lawn", 67: "West Englewood", 68: "Englewood",
  69: "Greater Grand Crossing", 70: "Ashburn", 71: "Auburn Gresham",
  72: "Beverly", 73: "Washington Heights", 74: "Mount Greenwood",
  75: "Morgan Park", 76: "O'Hare", 77: "Edgewater",
};

const SORTED_CAS = Object.entries(COMMUNITY_AREAS)
  .sort(([, a], [, b]) => a.localeCompare(b))
  .map(([id, name]) => ({ id: Number(id), name }));

const CLASS_FILTERS = [
  { key: "", label: "All" },
  { key: "residential", label: "Residential" },
  { key: "multi-family", label: "Multi-family" },
  { key: "commercial", label: "Commercial" },
  { key: "industrial", label: "Industrial" },
  { key: "vacant", label: "Vacant" },
] as const;

function classColor(cls: string): [number, number, number, number] {
  const prefix = cls.charAt(0);
  switch (prefix) {
    case "2": return [79, 195, 247, 200]; // residential — light blue
    case "3": return [126, 87, 194, 200]; // multi-family — purple
    case "5": return [255, 213, 79, 200]; // commercial — amber
    case "6": return [239, 83, 80, 200];  // industrial — red
    case "0":
    case "1": return [120, 144, 156, 180]; // vacant — gray
    default: return [160, 160, 160, 180];
  }
}

const PAGE_SIZE = 200;

const StarIcon = (
  <svg className="w-5 h-5 text-accent" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 16.8l-6.2 4.5 2.4-7.4L2 9.4h7.6z" />
  </svg>
);

export default function ExplorePage() {
  const { user } = useAuthContext();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const isPro = user?.tier === "premium" || user?.tier === "admin";

  const [selectedCA, setSelectedCA] = useState<number | null>(
    searchParams.get("ca") ? Number(searchParams.get("ca")) : null
  );
  const [classFilter, setClassFilter] = useState(searchParams.get("class") || "");
  const [tableData, setTableData] = useState<ExploreResponse | null>(null);
  const [mapParcels, setMapParcels] = useState<ExploreParcel[]>([]);
  const [mapTotal, setMapTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [mapLoading, setMapLoading] = useState(false);
  const [showUpgrade, setShowUpgrade] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hoveredPin, setHoveredPin] = useState<string | null>(null);

  const { containerRef, mapRef, overlayRef, mapReady } = useMapboxOverlay({
    center: [-87.6298, 41.8781],
    zoom: 10,
  });

  // Sync URL params
  useEffect(() => {
    const params: Record<string, string> = {};
    if (selectedCA) params.ca = String(selectedCA);
    if (classFilter) params.class = classFilter;
    setSearchParams(params, { replace: true });
  }, [selectedCA, classFilter, setSearchParams]);

  // Fetch table data
  const fetchTable = useCallback(async (ca: number, cls: string, off: number) => {
    if (!isPro) {
      setShowUpgrade(true);
      return;
    }
    setLoading(true);
    const result = await fetchExploreParcels({
      community_area: ca,
      class_prefix: cls || undefined,
      limit: PAGE_SIZE,
      offset: off,
    });
    if (result) setTableData(result);
    setLoading(false);
  }, [isPro]);

  // Fetch map data (all parcels up to 5000)
  const fetchMap = useCallback(async (ca: number, cls: string) => {
    if (!isPro) return;
    setMapLoading(true);
    const result = await fetchExploreMap({
      community_area: ca,
      class_prefix: cls || undefined,
    });
    if (result) {
      setMapParcels(result.parcels);
      setMapTotal(result.total);
    }
    setMapLoading(false);
  }, [isPro]);

  // On CA or class change, reset offset and fetch
  useEffect(() => {
    if (!selectedCA) return;
    setOffset(0);
    fetchTable(selectedCA, classFilter, 0);
    fetchMap(selectedCA, classFilter);
  }, [selectedCA, classFilter, fetchTable, fetchMap]);

  // On pagination change
  useEffect(() => {
    if (!selectedCA || offset === 0) return;
    fetchTable(selectedCA, classFilter, offset);
  }, [offset, selectedCA, classFilter, fetchTable]);

  // Fit bounds when CA changes
  useEffect(() => {
    if (!mapRef.current || !mapReady || !tableData?.bounds) return;
    const [minLat, minLon, maxLat, maxLon] = tableData.bounds;
    mapRef.current.fitBounds(
      [[minLon, minLat], [maxLon, maxLat]],
      { padding: 40, duration: 1200 }
    );
  }, [tableData?.bounds, mapReady, mapRef]);

  // Deck.gl layer
  const scatterLayer = useMemo(() => {
    if (!mapParcels.length) return null;
    return new ScatterplotLayer({
      id: "explore-parcels",
      data: mapParcels,
      getPosition: (d: ExploreParcel) => [d.lon, d.lat],
      getFillColor: (d: ExploreParcel) => classColor(d.class),
      getRadius: 8,
      radiusMinPixels: 2,
      radiusMaxPixels: 8,
      pickable: true,
      autoHighlight: true,
      highlightColor: [201, 100, 66, 255],
      onHover: (info) => {
        setHoveredPin(info.object ? (info.object as ExploreParcel).pin : null);
      },
      onClick: (info) => {
        if (info.object) {
          const p = info.object as ExploreParcel;
          navigate(`/scorecard?lat=${p.lat}&lon=${p.lon}`);
        }
      },
    });
  }, [mapParcels, navigate]);

  // Update deck.gl overlay
  useEffect(() => {
    if (!overlayRef.current) return;
    overlayRef.current.setProps({ layers: scatterLayer ? [scatterLayer] : [] });
  }, [scatterLayer, overlayRef]);

  const totalPages = tableData ? Math.ceil(tableData.total / PAGE_SIZE) : 0;
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  const hoveredParcel = hoveredPin ? mapParcels.find(p => p.pin === hoveredPin) : null;

  return (
    <div className="h-screen flex flex-col bg-dark-bg text-text-primary">
      {/* Header */}
      <header className="border-b border-dark-border bg-dark-surface/80 backdrop-blur-sm z-50 flex-shrink-0">
        <div className="max-w-[1920px] mx-auto px-4 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            {StarIcon}
            <span className="text-sm font-semibold tracking-tight">UrbanLayer</span>
          </Link>
          <nav className="flex items-center gap-4 text-[11px] text-text-muted">
            <Link to="/" className="hover:text-text-primary transition-colors">Chat</Link>
            <Link to="/scorecard" className="hover:text-text-primary transition-colors">Scorecard</Link>
            <span className="text-accent">Explore</span>
            <Link to="/about" className="hover:text-text-primary transition-colors">About</Link>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        {/* Left panel — filters + table */}
        <div className="w-full md:w-[400px] lg:w-[440px] flex-shrink-0 flex flex-col border-r border-dark-border overflow-hidden">
          {/* Filters */}
          <div className="p-4 border-b border-dark-border space-y-3 flex-shrink-0">
            <h1 className="text-lg font-semibold tracking-tight">Site Explorer</h1>
            <p className="text-[11px] text-text-muted">
              Browse parcels by community area and property class.
            </p>

            {/* Community area dropdown */}
            <div>
              <label className="block text-[10px] text-text-muted mb-1 uppercase tracking-wider">Community Area</label>
              <select
                value={selectedCA ?? ""}
                onChange={(e) => setSelectedCA(e.target.value ? Number(e.target.value) : null)}
                className="w-full bg-dark-elevated border border-dark-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent transition-colors appearance-none cursor-pointer"
              >
                <option value="">Select a community area...</option>
                {SORTED_CAS.map((ca) => (
                  <option key={ca.id} value={ca.id}>{ca.name}</option>
                ))}
              </select>
            </div>

            {/* Class filter */}
            <div>
              <label className="block text-[10px] text-text-muted mb-1.5 uppercase tracking-wider">Property Class</label>
              <div className="flex flex-wrap gap-1.5">
                {CLASS_FILTERS.map((f) => (
                  <button
                    key={f.key}
                    onClick={() => setClassFilter(f.key)}
                    className={`px-2.5 py-1 text-[11px] rounded-md border transition-colors ${
                      classFilter === f.key
                        ? "bg-accent/20 border-accent text-accent"
                        : "bg-dark-elevated border-dark-border text-text-secondary hover:border-text-muted"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Results */}
          <div className="flex-1 overflow-y-auto">
            {!selectedCA && (
              <div className="flex items-center justify-center h-full text-text-muted text-sm px-4 text-center">
                Select a community area to explore parcels
              </div>
            )}

            {selectedCA && loading && (
              <div className="p-4 space-y-2">
                {[...Array(8)].map((_, i) => (
                  <div key={i} className="h-10 bg-dark-elevated rounded animate-pulse" />
                ))}
              </div>
            )}

            {selectedCA && !loading && tableData && (
              <>
                {/* Count header */}
                <div className="px-4 py-2.5 border-b border-dark-border flex items-center justify-between">
                  <span className="text-[11px] text-text-secondary">
                    <span className="text-text-primary font-medium">{tableData.total.toLocaleString()}</span> parcels
                    {tableData.community_area_name && <> in <span className="text-text-primary">{tableData.community_area_name}</span></>}
                  </span>
                  {mapTotal > 5000 && (
                    <span className="text-[10px] text-text-muted">Map: {mapParcels.length.toLocaleString()} shown</span>
                  )}
                </div>

                {/* Table */}
                <table className="w-full text-left border-collapse">
                  <thead className="bg-dark-elevated/60 sticky top-0 z-10">
                    <tr>
                      <th className="px-4 py-2 text-[10px] font-semibold text-text-muted uppercase tracking-wider">PIN</th>
                      <th className="px-3 py-2 text-[10px] font-semibold text-text-muted uppercase tracking-wider">Class</th>
                      <th className="px-3 py-2 text-[10px] font-semibold text-text-muted uppercase tracking-wider hidden sm:table-cell">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tableData.parcels.map((p) => (
                      <tr
                        key={p.pin}
                        onClick={() => navigate(`/scorecard?lat=${p.lat}&lon=${p.lon}`)}
                        onMouseEnter={() => setHoveredPin(p.pin)}
                        onMouseLeave={() => setHoveredPin(null)}
                        className={`cursor-pointer border-t border-dark-border/50 transition-colors ${
                          hoveredPin === p.pin ? "bg-accent/10" : "hover:bg-dark-elevated/50"
                        }`}
                      >
                        <td className="px-4 py-2 text-[11px] font-mono text-text-primary">{p.pin}</td>
                        <td className="px-3 py-2 text-[11px] text-text-secondary">{p.class}</td>
                        <td className="px-3 py-2 text-[11px] text-text-muted hidden sm:table-cell truncate max-w-[180px]">{p.class_description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="px-4 py-3 border-t border-dark-border flex items-center justify-between flex-shrink-0">
                    <button
                      onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                      disabled={offset === 0}
                      className="px-3 py-1.5 text-[11px] bg-dark-elevated border border-dark-border rounded-md disabled:opacity-30 hover:border-text-muted transition-colors"
                    >
                      Previous
                    </button>
                    <span className="text-[11px] text-text-muted">
                      Page {currentPage} of {totalPages}
                    </span>
                    <button
                      onClick={() => setOffset(offset + PAGE_SIZE)}
                      disabled={currentPage >= totalPages}
                      className="px-3 py-1.5 text-[11px] bg-dark-elevated border border-dark-border rounded-md disabled:opacity-30 hover:border-text-muted transition-colors"
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Right panel — map */}
        <div className="flex-1 relative min-h-[300px]">
          <div ref={containerRef} className="absolute inset-0" />
          {mapLoading && (
            <div className="absolute top-3 left-3 z-10 bg-dark-surface/90 border border-dark-border rounded-lg px-3 py-1.5 text-[11px] text-text-secondary">
              Loading parcels...
            </div>
          )}
          {hoveredParcel && (
            <div className="absolute top-3 right-3 z-10 bg-dark-surface/95 border border-dark-border rounded-lg px-3 py-2 text-[11px] pointer-events-none">
              <div className="font-mono text-text-primary">{hoveredParcel.pin}</div>
              <div className="text-text-muted">{hoveredParcel.class_description}</div>
            </div>
          )}
          {!selectedCA && mapReady && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="bg-dark-surface/90 border border-dark-border rounded-xl px-6 py-4 text-center">
                <div className="text-sm text-text-secondary mb-1">Select a community area</div>
                <div className="text-[11px] text-text-muted">Parcels will appear on the map</div>
              </div>
            </div>
          )}

          {/* Legend */}
          {mapParcels.length > 0 && (
            <div className="absolute bottom-6 left-3 z-10 bg-dark-surface/95 border border-dark-border rounded-lg px-3 py-2 space-y-1">
              <div className="text-[9px] text-text-muted uppercase tracking-wider mb-1">Property Class</div>
              {[
                { label: "Residential", color: "#4fc3f7" },
                { label: "Multi-family", color: "#7e57c2" },
                { label: "Commercial", color: "#ffd54f" },
                { label: "Industrial", color: "#ef5350" },
                { label: "Vacant", color: "#78909c" },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-2 text-[10px] text-text-secondary">
                  <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
                  {item.label}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {showUpgrade && (
        <UpgradePrompt
          feature="Site Explorer"
          onClose={() => setShowUpgrade(false)}
        />
      )}
    </div>
  );
}
