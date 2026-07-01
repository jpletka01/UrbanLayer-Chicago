// Mapbox Static Images helper — a real dark-v11 Chicago basemap for the landing (no GL needed).
// Returns null when the token is absent so callers can fall back gracefully.
const TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;

interface StaticMapOpts {
  lon: number;
  lat: number;
  zoom?: number;
  width?: number;
  height?: number;
  /** Drop an accent pin at the center. */
  pin?: boolean;
}

export function staticMapUrl({ lon, lat, zoom = 13, width = 640, height = 640, pin = false }: StaticMapOpts): string | null {
  if (!TOKEN) return null;
  const overlay = pin ? `pin-l+f9a474(${lon},${lat})/` : "";
  return `https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/${overlay}${lon},${lat},${zoom},0/${width}x${height}@2x?access_token=${TOKEN}&logo=false&attribution=false`;
}

// A recognizable parcel + a wider city view for the two landing surfaces.
export const CHI_PARCEL = { lon: -87.6795, lat: 41.9105 }; // 1601 N Milwaukee Ave
export const CHI_CITY = { lon: -87.647, lat: 41.9 }; // near the river / near-north grid
