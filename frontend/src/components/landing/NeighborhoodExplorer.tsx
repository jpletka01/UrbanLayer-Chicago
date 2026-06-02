import { motion, useInView } from "motion/react";
import { useCallback, useRef, useState } from "react";
import type { MapData, SourceTag } from "../../lib/types";
import { fetchMapData } from "../../lib/api";
import { getDummyMapData, DUMMY_COMMUNITY_AREA_NAME } from "../../lib/dummyData";
import { NeighborhoodSelector } from "./NeighborhoodSelector";
import { DataSourceTabs, type LandingSource } from "./DataSourceTabs";
import { LandingMap } from "./LandingMap";
import { LandingAnalytics } from "./LandingAnalytics";

const SOURCE_MAP: Record<LandingSource, SourceTag[]> = {
  all: ["crime_api", "311_api", "permits_api"],
  crime: ["crime_api"],
  "311": ["311_api"],
  permits: ["permits_api"],
};

export function NeighborhoodExplorer() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });

  const [mapData, setMapData] = useState<MapData>(getDummyMapData());
  const [source, setSource] = useState<LandingSource>("all");
  const [loading, setLoading] = useState(false);
  const [isDummy, setIsDummy] = useState(true);

  const handleSelect = useCallback(async (communityArea: number, _name: string) => {
    setIsDummy(false);
    setLoading(true);
    const data = await fetchMapData({
      community_area: communityArea,
      time_range_days: 30,
      sources: SOURCE_MAP[source],
    });
    if (data) {
      setMapData(data);
    }
    setLoading(false);
  }, [source]);

  const handleSourceChange = useCallback(async (s: LandingSource) => {
    setSource(s);
  }, []);

  return (
    <section ref={ref} className="py-20 px-6 bg-dark-bg">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={inView ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.5 }}
        className="max-w-6xl mx-auto space-y-8"
      >
        {/* Header */}
        <div className="text-center space-y-3">
          <h2 className="text-2xl md:text-3xl font-semibold text-text-primary">
            Explore a neighborhood
          </h2>
          <p className="text-text-secondary text-sm max-w-lg mx-auto">
            Pick a community area or enter an address to explore live city data — crime patterns, 311 service requests, building permits, and month-over-month trends, updated from the Chicago Data Portal.
          </p>
        </div>

        {/* Controls */}
        <div className="space-y-4">
          <NeighborhoodSelector
            onSelect={handleSelect}
            loading={loading}
          />
          <div className="flex items-center justify-center gap-4">
            <DataSourceTabs active={source} onChange={handleSourceChange} />
            {isDummy && (
              <span className="text-xs text-text-muted">
                Showing sample data &mdash; {DUMMY_COMMUNITY_AREA_NAME}
              </span>
            )}
          </div>
        </div>

        {/* Results: Map + Analytics side by side */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6" style={{ minHeight: "420px" }}>
          <div className="h-[420px] md:h-auto">
            <LandingMap mapData={mapData} source={source} loading={loading} />
          </div>
          <div className="space-y-4">
            <LandingAnalytics mapData={mapData} source={source} />
          </div>
        </div>
      </motion.div>
    </section>
  );
}
