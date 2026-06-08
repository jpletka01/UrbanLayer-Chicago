import i18n from "./i18n";
import { OVERLAY_INFO, ZONE_INFO } from "./mapColors";

export interface TermInfo {
  label: string;
  description: string;
  bullets: string[];
}

const FLAG_TO_OVERLAY: Record<string, string> = {
  in_planned_development: "planned_development",
  in_landmark_district: "landmark_district",
  is_landmark_building: "landmark_building",
  in_historic_district: "historic_district",
  on_national_register: "national_register",
  in_lakefront_protection: "lakefront_protection",
  on_pedestrian_street: "pedestrian_street",
  in_special_district: "special_district",
  in_pmd: "pmd_subarea",
  in_tod_area: "tod_combined",
  in_adu_area: "adu_area",
  in_aro_zone: "aro_zone",
  in_ssa: "ssa",
};

function tryTranslatedZone(prefix: string): TermInfo | null {
  const labelKey = `map:zones.${prefix}.label`;
  const label = i18n.t(labelKey);
  if (label === labelKey) return null;
  const descKey = `map:zones.${prefix}.description`;
  const desc = i18n.t(descKey);
  const examples = i18n.t(`map:zones.${prefix}.examples`, { returnObjects: true });
  return {
    label,
    description: desc !== descKey ? desc : "",
    bullets: Array.isArray(examples) ? examples : [],
  };
}

function tryTranslatedOverlay(overlayKey: string): TermInfo | null {
  const labelKey = `map:overlays.${overlayKey}.label`;
  const label = i18n.t(labelKey);
  if (label === labelKey) return null;
  const descKey = `map:overlays.${overlayKey}.description`;
  const desc = i18n.t(descKey);
  const implications = i18n.t(`map:overlays.${overlayKey}.implications`, { returnObjects: true });
  return {
    label,
    description: desc !== descKey ? desc : "",
    bullets: Array.isArray(implications) ? implications : [],
  };
}

function tryTranslatedIncentive(key: string): TermInfo | null {
  const labelKey = `data:terms.incentives.${key}.label`;
  const label = i18n.t(labelKey);
  if (label === labelKey) return null;
  const descKey = `data:terms.incentives.${key}.description`;
  const desc = i18n.t(descKey);
  const bullets = i18n.t(`data:terms.incentives.${key}.bullets`, { returnObjects: true });
  return {
    label,
    description: desc !== descKey ? desc : "",
    bullets: Array.isArray(bullets) ? bullets : [],
  };
}

function tryTranslatedFloodZone(zone: string): TermInfo | null {
  const labelKey = `data:terms.floodZones.${zone}.label`;
  const label = i18n.t(labelKey);
  if (label === labelKey) return null;
  const descKey = `data:terms.floodZones.${zone}.description`;
  const desc = i18n.t(descKey);
  const bullets = i18n.t(`data:terms.floodZones.${zone}.bullets`, { returnObjects: true });
  return {
    label,
    description: desc !== descKey ? desc : "",
    bullets: Array.isArray(bullets) ? bullets : [],
  };
}

function tryTranslatedExtraOverlay(key: string): TermInfo | null {
  const labelKey = `data:terms.extraOverlays.${key}.label`;
  const label = i18n.t(labelKey);
  if (label === labelKey) return null;
  const descKey = `data:terms.extraOverlays.${key}.description`;
  const desc = i18n.t(descKey);
  const bullets = i18n.t(`data:terms.extraOverlays.${key}.bullets`, { returnObjects: true });
  return {
    label,
    description: desc !== descKey ? desc : "",
    bullets: Array.isArray(bullets) ? bullets : [],
  };
}

const INCENTIVE_KEYS = ["tif_district", "opportunity_zone", "enterprise_zone"];

export function getTermInfo(key: string): TermInfo | null {
  if (key.startsWith("zone:")) {
    const prefix = key.slice(5);
    const translated = tryTranslatedZone(prefix);
    if (translated) return translated;
    const z = ZONE_INFO[prefix];
    if (!z) return null;
    return { label: z.label, description: z.description, bullets: z.examples };
  }

  if (key.startsWith("flood:")) {
    const zone = key.slice(6).toUpperCase();
    const translated = tryTranslatedFloodZone(zone);
    if (translated) return translated;
    return null;
  }

  if (INCENTIVE_KEYS.includes(key)) {
    const translated = tryTranslatedIncentive(key);
    if (translated) return translated;
    return null;
  }

  if (key in FLAG_TO_OVERLAY) {
    const overlayKey = FLAG_TO_OVERLAY[key];
    const extra = tryTranslatedExtraOverlay(overlayKey);
    if (extra) return extra;
    const translated = tryTranslatedOverlay(overlayKey);
    if (translated) return translated;
    const ov = OVERLAY_INFO[overlayKey];
    if (!ov) return null;
    return { label: ov.label, description: ov.description, bullets: ov.implications };
  }

  if (key in OVERLAY_INFO) {
    const translated = tryTranslatedOverlay(key);
    if (translated) return translated;
    const ov = OVERLAY_INFO[key];
    return { label: ov.label, description: ov.description, bullets: ov.implications };
  }

  if (key in ZONE_INFO) {
    const translated = tryTranslatedZone(key);
    if (translated) return translated;
    const z = ZONE_INFO[key];
    return { label: z.label, description: z.description, bullets: z.examples };
  }

  return null;
}
