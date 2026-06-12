import i18n from "i18next";
import type {
  Message,
  ContextObject,
  CodeChunk,
  PropertySummary,
  RegulatorySummary,
  IncentivesSummary,
  NeighborhoodSummary,
  CrimeSummary,
  ThreeOneOneSummary,
  PermitSummary,
  ViolationSummary,
  BusinessSummary,
} from "./types";

function tr(key: string, opts?: Record<string, unknown>): string {
  return i18n.t(`report.${key}`, { ns: "data", ...opts });
}

export interface ReportSection {
  type:
    | "header"
    | "map"
    | "property"
    | "regulatory"
    | "incentives"
    | "neighborhood"
    | "safety"
    | "qa"
    | "sources"
    | "disclaimer";
  title: string;
  content: unknown;
}

export interface ReportData {
  title: string;
  address: string | null;
  communityArea: string | null;
  generatedAt: string;
  sections: ReportSection[];
  mapScreenshotDataUrl: string | null;
}

function stripMarkdown(text: string): string {
  return text
    .replace(/\[(\d+)\]/g, "[$1]")
    .replace(/\[data:[^\]]+\]/g, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/#{1,6}\s/g, "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}

function findLatest<T>(
  messages: Message[],
  extract: (ctx: ContextObject) => T | null | undefined,
): T | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const ctx = messages[i].context;
    if (!ctx) continue;
    const val = extract(ctx);
    if (val != null) return val;
  }
  return null;
}

function collectCodeChunks(messages: Message[]): CodeChunk[] {
  const seen = new Set<string>();
  const chunks: CodeChunk[] = [];
  for (const m of messages) {
    for (const c of m.context?.code_chunks ?? []) {
      const key = c.section;
      if (!seen.has(key)) {
        seen.add(key);
        chunks.push(c);
      }
    }
  }
  return chunks;
}

function formatCurrency(n: number): string {
  const locale = i18n.language === "es" ? "es-ES" : "en-US";
  return n.toLocaleString(locale, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function buildPropertySection(prop: PropertySummary): ReportSection {
  return {
    type: "property",
    title: tr("propertySummary"),
    content: prop,
  };
}

function buildRegulatorySection(reg: RegulatorySummary): ReportSection {
  return {
    type: "regulatory",
    title: tr("regulatoryOverview"),
    content: reg,
  };
}

function buildIncentivesSection(inc: IncentivesSummary): ReportSection {
  return {
    type: "incentives",
    title: tr("incentivePrograms"),
    content: inc,
  };
}

function buildNeighborhoodSection(nb: NeighborhoodSummary): ReportSection {
  return {
    type: "neighborhood",
    title: tr("neighborhoodProfile"),
    content: nb,
  };
}

function buildSafetySection(
  crime: CrimeSummary | null,
  three11: ThreeOneOneSummary | null,
  permits: PermitSummary | null,
  violations: ViolationSummary | null,
  businesses: BusinessSummary | null,
): ReportSection {
  return {
    type: "safety",
    title: tr("safetyActivity"),
    content: { crime, three11, permits, violations, businesses },
  };
}

export function buildReportData(
  messages: Message[],
  mapScreenshot: string | null,
  conversationTitle: string,
): ReportData {
  const sections: ReportSection[] = [];
  const latestCtx = findLatest(messages, (c) => c);

  const address = latestCtx?.resolved_address ?? null;
  const communityArea = latestCtx?.community_area_name ?? null;

  const locale = i18n.language === "es" ? "es-ES" : "en-US";
  sections.push({
    type: "header",
    title: tr("siteReport"),
    content: { address, communityArea, generatedAt: new Date().toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" }) },
  });

  if (mapScreenshot) {
    sections.push({ type: "map", title: tr("locationMap"), content: mapScreenshot });
  }

  const property = findLatest(messages, (c) => c.property);
  if (property) sections.push(buildPropertySection(property));

  const regulatory = findLatest(messages, (c) => c.regulatory);
  if (regulatory) sections.push(buildRegulatorySection(regulatory));

  const incentives = findLatest(messages, (c) => c.incentives);
  if (incentives) sections.push(buildIncentivesSection(incentives));

  const neighborhood = findLatest(messages, (c) => c.neighborhood);
  if (neighborhood) sections.push(buildNeighborhoodSection(neighborhood));

  const crime = findLatest(messages, (c) => c.crime_last_90d);
  const three11 = findLatest(messages, (c) => c.open_311_requests);
  const permits = findLatest(messages, (c) => c.permits);
  const violations = findLatest(messages, (c) => c.violations);
  const businesses = findLatest(messages, (c) => c.businesses);
  if (crime || three11 || permits || violations || businesses) {
    sections.push(buildSafetySection(crime, three11, permits, violations, businesses));
  }

  const qaPairs: Array<{ question: string; answer: string }> = [];
  for (let i = 0; i < messages.length; i++) {
    if (messages[i].role === "user" && i + 1 < messages.length && messages[i + 1].role === "assistant") {
      qaPairs.push({
        question: messages[i].content,
        answer: stripMarkdown(messages[i + 1].content),
      });
    }
  }
  if (qaPairs.length > 0) {
    sections.push({ type: "qa", title: tr("conversationTranscript"), content: qaPairs });
  }

  const codeChunks = collectCodeChunks(messages);
  if (codeChunks.length > 0) {
    sections.push({ type: "sources", title: tr("municipalCodeCitations"), content: codeChunks });
  }

  const hasDisclaimer = messages.some((m) => m.context?.requires_disclaimer);
  const dataLagDays = latestCtx?.data_lag_days;
  const dataLagCutoff = latestCtx?.data_lag_cutoff;
  const dataLag = dataLagDays && dataLagCutoff
    ? i18n.t("crimeDataLag", { ns: "data", days: dataLagDays, cutoff: dataLagCutoff })
    : latestCtx?.data_lag_note;
  if (hasDisclaimer || dataLag) {
    sections.push({
      type: "disclaimer",
      title: tr("disclaimersProvenance"),
      content: { hasDisclaimer, dataLag, dataAsOf: latestCtx?.data_as_of },
    });
  }

  return {
    title: conversationTitle || `${address || communityArea || "Chicago"} Transcript`,
    address,
    communityArea,
    generatedAt: new Date().toISOString(),
    sections,
    mapScreenshotDataUrl: mapScreenshot,
  };
}

export { formatCurrency };
