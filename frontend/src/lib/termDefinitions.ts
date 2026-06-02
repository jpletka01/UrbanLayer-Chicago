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

const INCENTIVE_INFO: Record<string, TermInfo> = {
  tif_district: {
    label: "TIF District",
    description: "Tax Increment Financing district that captures property tax growth to fund local improvements like infrastructure, streetscape, and development incentives.",
    bullets: [
      "23-year lifespan from creation date",
      "Does not increase your individual tax rate",
      "Funds neighborhood infrastructure and development",
      "Expiring TIFs return increment to all taxing bodies",
    ],
  },
  opportunity_zone: {
    label: "Opportunity Zone",
    description: "Federal tax incentive (2017 Tax Cuts & Jobs Act) encouraging long-term capital investment in low-income census tracts.",
    bullets: [
      "Capital gains tax deferral on qualified investments",
      "10-year hold can eliminate gains on new investment",
      "Investments made through Qualified Opportunity Funds (QOFs)",
      "Designated through 2028",
    ],
  },
  enterprise_zone: {
    label: "Enterprise Zone",
    description: "State of Illinois designated area offering tax incentives to businesses that invest and create jobs in economically distressed communities.",
    bullets: [
      "Sales tax exemption on building materials",
      "State investment tax credits",
      "Utility tax exemptions available",
      "Must create or retain jobs to qualify",
    ],
  },
};

const FLOOD_ZONE_INFO: Record<string, TermInfo> = {
  X: {
    label: "Zone X — Minimal Risk",
    description: "Area outside the 100-year and 500-year floodplains. Lowest flood risk designation.",
    bullets: ["Flood insurance not required (but available)", "No special construction requirements"],
  },
  A: {
    label: "Zone A — High Risk",
    description: "Within the 100-year floodplain. 1% annual chance of flooding, 26% chance over a 30-year mortgage.",
    bullets: ["Flood insurance required for federally-backed mortgages", "Base Flood Elevation (BFE) not determined"],
  },
  AE: {
    label: "Zone AE — High Risk (Detailed)",
    description: "Within the 100-year floodplain with detailed Base Flood Elevations determined by engineering study.",
    bullets: ["Flood insurance required", "Elevated construction required above BFE", "Detailed floodway analysis available"],
  },
  AH: {
    label: "Zone AH — Shallow Flooding",
    description: "Area of 100-year shallow flooding with depths of 1–3 feet, typically ponding areas.",
    bullets: ["Flood insurance required", "Flood depths 1–3 feet", "Special drainage considerations"],
  },
  AO: {
    label: "Zone AO — Sheet Flow",
    description: "Area of 100-year shallow flooding with sheet flow on sloped terrain, depths of 1–3 feet.",
    bullets: ["Flood insurance required", "Sheet flow rather than ponding", "Drainage path considerations"],
  },
  VE: {
    label: "Zone VE — Coastal High Risk",
    description: "Coastal area with 100-year flood risk including wave action. Highest-risk designation.",
    bullets: ["Flood insurance required", "Strictest construction standards", "Elevated on pilings required"],
  },
};

const EXTRA_OVERLAY: Record<string, TermInfo> = {
  tod_combined: {
    label: "Transit-Oriented Development (TOD)",
    description: "Zone near CTA or Metra rail stations encouraging dense, mixed-use development with reduced parking.",
    bullets: ["Reduced parking requirements", "Density bonuses available", "Pedestrian-oriented design standards"],
  },
};

export function getTermInfo(key: string): TermInfo | null {
  if (key.startsWith("zone:")) {
    const prefix = key.slice(5);
    const z = ZONE_INFO[prefix];
    if (!z) return null;
    return { label: z.label, description: z.description, bullets: z.examples };
  }

  if (key.startsWith("flood:")) {
    const zone = key.slice(6).toUpperCase();
    return FLOOD_ZONE_INFO[zone] ?? null;
  }

  if (key in INCENTIVE_INFO) return INCENTIVE_INFO[key];

  if (key in FLAG_TO_OVERLAY) {
    const overlayKey = FLAG_TO_OVERLAY[key];
    if (overlayKey in EXTRA_OVERLAY) return EXTRA_OVERLAY[overlayKey];
    const ov = OVERLAY_INFO[overlayKey];
    if (!ov) return null;
    return { label: ov.label, description: ov.description, bullets: ov.implications };
  }

  if (key in OVERLAY_INFO) {
    const ov = OVERLAY_INFO[key];
    return { label: ov.label, description: ov.description, bullets: ov.implications };
  }

  if (key in ZONE_INFO) {
    const z = ZONE_INFO[key];
    return { label: z.label, description: z.description, bullets: z.examples };
  }

  return null;
}
