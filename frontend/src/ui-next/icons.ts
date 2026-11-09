// One icon per concept, everywhere in the new UI (decision Item 75, standard 1). Lucide only (pinned
// lucide-react), 1.5 stroke. A new concept gets one line here before it gets a component.
import {
  ArrowUpToLine, BadgeDollarSign, BookOpen, Bookmark, Building2, ChartColumn, HandCoins, KeyRound, CircleUser, Download, FileClock, LandPlot, Layers,
  Footprints, ListChecks, Map as MapIcon, MessageCircle, MessageCircleQuestion, Receipt, Ruler, Search, Square, type LucideIcon,
} from "lucide-react";
import type { NavIcon } from "./readiness";

export const ICON = {
  // destinations
  search: Search,
  discovery: MapIcon,
  saved: Bookmark,
  chat: MessageCircle,
  account: CircleUser,
  // the Profile's tools (icon-only buttons are allowed for these three; Item 75)
  ask: MessageCircleQuestion, // a chat bubble (owner review 2026-11-07), the same "ask" icon as today's ToolTray
  sources: BookOpen,
  export: Download,
  // facts
  units: Building2,
  zoning: LandPlot,
  tax: Receipt,
  pricePerSqft: Ruler,
  floorArea: Layers,
  height: ArrowUpToLine,
  lot: Square,
  pending: FileClock,
  rules: ListChecks,
  sale: BadgeDollarSign,
  walk: Footprints,
  valueOverTime: ChartColumn,
  rent: KeyRound,
  incentives: HandCoins,
} satisfies Record<string, LucideIcon>;

export const NAV_ICON: Record<NavIcon, LucideIcon> = {
  search: ICON.search,
  discovery: ICON.discovery,
  saved: ICON.saved,
  chat: ICON.chat,
};

export const STROKE = 1.5;
