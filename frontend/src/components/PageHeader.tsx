import FloatingNav from "./FloatingNav";

// PageHeader is now a thin wrapper over the unified FloatingNav (floating pill). Kept so the
// Scorecard/Discovery/Pricing/About consumers keep rendering `<PageHeader />` unchanged, and
// `navItemsFor` keeps its stable import path for PageHeader.nav.test.ts.
export { navItemsFor } from "./FloatingNav";

/**
 * Standard header for the non-chat pages (Scorecard, Discovery, Pricing, About): the floating
 * nav pill. `sticky` is accepted for back-compat (the pill is always sticky-at-top-3); pass a
 * wider `maxWidthClass` on data-dense pages (Discovery).
 */
export default function PageHeader({
  maxWidthClass = "max-w-7xl",
}: {
  sticky?: boolean;
  maxWidthClass?: string;
}) {
  return <FloatingNav position="floating" languageVariant="workspace" maxWidthClass={maxWidthClass} />;
}
