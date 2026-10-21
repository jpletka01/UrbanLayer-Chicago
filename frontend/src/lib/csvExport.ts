import type { ComparablesSummary, ContextObject } from "./types";
import type { Provenance } from "./api";
import i18n from "./i18n";
import { displayState, plainCaption } from "./confidence";

interface CSVColumn<T> {
  key: keyof T & string;
  header: string;
}

function escapeCell(value: unknown): string {
  if (value == null) return "";
  const str = typeof value === "boolean" ? (value ? "Yes" : "No") : String(value);
  if (str.includes(",") || str.includes('"') || str.includes("\n") || str.includes("\r")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export function toCSV<T extends object>(
  rows: T[],
  columns?: CSVColumn<T>[],
): string {
  if (rows.length === 0) return "";
  const cols = columns ?? (Object.keys(rows[0] as Record<string, unknown>) as (keyof T & string)[]).map((k) => ({ key: k, header: k }));
  const header = cols.map((c) => escapeCell(c.header)).join(",");
  const body = rows.map((row) => cols.map((c) => escapeCell((row as Record<string, unknown>)[c.key])).join(",")).join("\n");
  return `${header}\n${body}`;
}

export function downloadCSV(csv: string, filename: string): void {
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function exportCSV<T extends object>(
  rows: T[],
  filename: string,
  columns?: CSVColumn<T>[],
): void {
  downloadCSV(toCSV(rows, columns), filename);
}

export function buildFilenameSlug(label: string): string {
  return label.replace(/[^a-zA-Z0-9]+/g, "_").toLowerCase().slice(0, 40);
}

function dictToRows(dict: Record<string, number>): { key: string; value: number }[] {
  return Object.entries(dict)
    .sort((a, b) => b[1] - a[1])
    .map(([key, value]) => ({ key, value }));
}

function addSection(parts: string[], title: string, csv: string): void {
  if (!csv) return;
  parts.push(`${title}`);
  parts.push(csv);
  parts.push("");
}

interface FactRow { field: string; value: unknown; fact?: string }

/** Rows with the source columns a reader needs to check a figure: who published it, how far to
    trust it, as of when, and the same caption the page prints. A withheld figure is blank, with
    the reason in the note. Sheets without provenance keep two columns. */
function factRows(rows: FactRow[], prov: Record<string, Provenance> | null | undefined) {
  const tEn = i18n.getFixedT("en", "common");
  return rows.map(({ field, value, fact }) => {
    const e = fact ? prov?.[fact] : undefined;
    return {
      field,
      value: e && displayState(e) === "withheld" ? "" : value,
      source: e?.source_id ?? "",
      authority: e?.tier ? tEn(`confidence.tier.${e.tier}`) : "",
      as_of: e?.as_of ?? e?.period ?? "",
      note: plainCaption(e, tEn),
    };
  });
}

const FACT_COLUMNS = [
  { key: "source", header: "Source" },
  { key: "authority", header: "Authority" },
  { key: "as_of", header: "As of" },
  { key: "note", header: "Note" },
] as const;

export function buildScorecardCSV(
  ctx: ContextObject, address: string, comparables?: ComparablesSummary | null,
  provenance?: Record<string, Provenance> | null,
): string {
  const parts: string[] = [];
  const date = new Date().toISOString().slice(0, 10);

  // Header
  parts.push(`Property Profile — ${address}`);
  parts.push(`Generated,${date}`);
  parts.push("");

  // Property Summary
  if (ctx.property) {
    const p = ctx.property;
    const kvRows = factRows([
      { field: "PIN", value: p.pin14 ?? "" },
      { field: "Address", value: p.address ?? "" },
      { field: "Building Class", value: p.bldg_class ?? "" },
      { field: "Class Description", value: p.bldg_class_description ?? "" },
      { field: "Building Sqft", value: p.bldg_sqft ?? "", fact: "property.bldg_sqft" },
      { field: "Land Sqft", value: p.land_sqft ?? "", fact: "property.land_sqft" },
      { field: "Stories", value: p.stories ?? "", fact: "property.stories" },
      { field: "Units", value: p.units ?? "", fact: "property.units" },
      { field: "Rooms", value: p.rooms ?? "" },
      { field: "Bedrooms", value: p.bedrooms ?? "" },
      { field: "Full Baths", value: p.full_baths ?? "" },
      { field: "Half Baths", value: p.half_baths ?? "" },
      { field: "Building Age", value: p.bldg_age ?? "", fact: "property.year_built" },
      { field: "Total Assessed Value", value: p.total_assessed_value ?? "", fact: "property.assessed_value" },
      { field: "Implied Market Value", value: p.implied_market_value ?? "", fact: "property.implied_market_value" },
      { field: "Estimated Annual Tax", value: p.estimated_annual_tax ?? "", fact: "property.tax_estimate" },
      { field: "Tax Year", value: p.tax_year ?? "" },
      { field: "Effective Tax Rate", value: p.effective_tax_rate != null ? `${(p.effective_tax_rate * 100).toFixed(2)}%` : "", fact: "property.effective_rate" },
    ], provenance);
    addSection(parts, "Property Summary", toCSV(kvRows, [
      { key: "field", header: "Field" },
      { key: "value", header: "Value" },
      ...FACT_COLUMNS,
    ]));

    if (p.assessment_history.length > 0) {
      addSection(parts, "Assessment History", toCSV(p.assessment_history, [
        { key: "year", header: "Year" },
        { key: "land", header: "Land Value" },
        { key: "building", header: "Building Value" },
        { key: "total", header: "Total Value" },
      ]));
    }

    if (p.sales_history.length > 0) {
      addSection(parts, "Sales History", toCSV(p.sales_history, [
        { key: "date", header: "Date" },
        { key: "price", header: "Price" },
        { key: "deed_type", header: "Deed Type" },
      ]));
    }

    if (p.tax_breakdown.length > 0) {
      addSection(parts, "Tax Breakdown", toCSV(p.tax_breakdown, [
        { key: "agency", header: "Agency" },
        { key: "rate", header: "Rate" },
        { key: "amount", header: "Amount" },
      ]));
    }
  }

  // Comparable Sales
  if (comparables && comparables.sales.length > 0) {
    const summaryRows = factRows([
      { field: "Median Sale Price", value: comparables.median_sale_price ?? "", fact: "property.comps.median_price" },
      { field: "Median $/Land Sqft", value: comparables.median_price_per_land_sqft ?? "", fact: "property.comps.median_price_per_land_sqft" },
      { field: "Median $/Bldg Sqft", value: comparables.median_price_per_bldg_sqft ?? "", fact: "property.comps.median_price_per_bldg_sqft" },
      { field: "Price Range Min", value: comparables.price_range_min ?? "" },
      { field: "Price Range Max", value: comparables.price_range_max ?? "" },
      { field: "Sales Volume", value: comparables.sales_volume },
    ], provenance);
    addSection(parts, "Comparable Sales Summary", toCSV(summaryRows, [
      { key: "field", header: "Metric" },
      { key: "value", header: "Value" },
      ...FACT_COLUMNS,
    ]));

    const salesRows = comparables.sales.map(s => ({
      pin: s.pin,
      date: s.sale_date ?? "",
      price: s.sale_price ?? "",
      land_sqft: s.land_sqft ?? "",
      bldg_sqft: s.bldg_sqft ?? "",
      price_per_land_sqft: s.price_per_land_sqft ?? "",
      price_per_bldg_sqft: s.price_per_bldg_sqft ?? "",
      distance_mi: s.distance_mi ?? "",
      deed_type: s.deed_type ?? "",
    }));
    addSection(parts, "Comparable Sales Detail", toCSV(salesRows, [
      { key: "pin", header: "PIN" },
      { key: "date", header: "Date" },
      { key: "price", header: "Price" },
      { key: "land_sqft", header: "Land Sqft" },
      { key: "bldg_sqft", header: "Bldg Sqft" },
      { key: "price_per_land_sqft", header: "$/Land Sqft" },
      { key: "price_per_bldg_sqft", header: "$/Bldg Sqft" },
      { key: "distance_mi", header: "Distance (mi)" },
      { key: "deed_type", header: "Deed Type" },
    ]));
  }

  // Violations
  if (ctx.violations && Object.keys(ctx.violations.by_category).length > 0) {
    const rows = dictToRows(ctx.violations.by_category);
    addSection(parts, `Violations (${ctx.violations.total} total, ${ctx.violations.open_count} open)`, toCSV(rows, [
      { key: "key", header: "Category" },
      { key: "value", header: "Count" },
    ]));
  }

  // Crime
  if (ctx.crime_last_90d && Object.keys(ctx.crime_last_90d.by_type).length > 0) {
    const rows = dictToRows(ctx.crime_last_90d.by_type);
    addSection(parts, `Crime (${ctx.crime_last_90d.total} incidents, 90 days)`, toCSV(rows, [
      { key: "key", header: "Type" },
      { key: "value", header: "Count" },
    ]));
  }

  // 311
  if (ctx.open_311_requests && Object.keys(ctx.open_311_requests.by_department).length > 0) {
    const rows = dictToRows(ctx.open_311_requests.by_department);
    addSection(parts, `311 Requests (${ctx.open_311_requests.total} total)`, toCSV(rows, [
      { key: "key", header: "Department" },
      { key: "value", header: "Count" },
    ]));
  }

  // Permits
  if (ctx.permits && Object.keys(ctx.permits.by_type).length > 0) {
    const rows = dictToRows(ctx.permits.by_type);
    addSection(parts, `Permits (${ctx.permits.total} total, $${ctx.permits.total_estimated_cost.toLocaleString()})`, toCSV(rows, [
      { key: "key", header: "Type" },
      { key: "value", header: "Count" },
    ]));
  }

  // Businesses
  if (ctx.businesses && Object.keys(ctx.businesses.by_license_type).length > 0) {
    const rows = dictToRows(ctx.businesses.by_license_type);
    addSection(parts, `Businesses (${ctx.businesses.total} total)`, toCSV(rows, [
      { key: "key", header: "License Type" },
      { key: "value", header: "Count" },
    ]));
  }

  // Demographics
  if (ctx.neighborhood?.demographics) {
    const d = ctx.neighborhood.demographics;
    const kvRows = [
      { field: "Community Area", value: d.community_area_name ?? "" },
      { field: "Population", value: d.population ?? "" },
      { field: "Median Household Income (estimated from 5 brackets)", value: d.median_household_income ?? "" },
      { field: "ACS Period", value: d.acs_period ?? "" },
    ];
    addSection(parts, "Demographics", toCSV(kvRows, [
      { key: "field", header: "Metric" },
      { key: "value", header: "Value" },
    ]));
  }

  return parts.join("\n");
}
