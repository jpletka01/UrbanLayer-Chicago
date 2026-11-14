import type { Amendment, CodeCurrency } from "../../lib/types";

export const tod: Amendment = {
  record: "SO2026-0025391", passed_on: "2026-10-14", title: "Amendment of Title 17 regarding TOD streets",
  summary: "Adds §17-3-0600: transit-served location rules along designated TOD streets.", sections: ["17-3-0308", "17-3-0600"],
  url: "https://chicityclerkelms.chicago.gov/Matter/?matterId=tod", relevance: "title17", review_status: "reviewed",
  product_effect: "applied", codified: false, parcel_relevant: false,
};
export const lawrence: Amendment = {
  record: "O2026-0026042", passed_on: "2026-09-23", title: "Amendment of Title 17 regarding pedestrian streets", summary: null,
  sections: ["17-3-0503-D"], url: "https://chicityclerkelms.chicago.gov/Matter/?matterId=ped", relevance: "title17",
  review_status: "unreviewed", product_effect: "pending", codified: false, parcel_relevant: true,
};
export const noEffect: Amendment = {
  record: "O2026-0000001", passed_on: "2026-08-01", title: "Amendment of Title 17 regarding signs", summary: "Sign permits only.",
  sections: ["17-12-1000"], url: null, relevance: "title17", review_status: "reviewed", product_effect: "none", codified: false,
};

export const currency = (over: Partial<CodeCurrency> = {}): CodeCurrency => ({
  current_through: "2026-06-17", label: "Council Journal of June 17, 2026", checked_at: "2026-10-20T11:00:00Z",
  check_state: "fresh", since: { title17: 3, cited_other: 0 }, clerk_url: "https://chicityclerkelms.chicago.gov/Legislation/",
  amendments: [lawrence, tod, noEffect], ...over,
});
