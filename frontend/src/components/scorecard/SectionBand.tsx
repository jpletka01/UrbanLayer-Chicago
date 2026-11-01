// The Profile's ONE sticky band (redesign plan §4, decision Item 50; Jack's second pass, item 7: the
// floating verdict strip covered the section nav). Desktop: the section nav, with a compact neutral
// verdict label at its left edge, sticks under the site nav. Nothing else floats over the page. Phone:
// the sticky element is a bottom action bar (verdict label + Ask the analyst) and the dock's floating
// launcher hides below `md`, so there is still one.
import { useTranslation } from "react-i18next";
import { Button } from "../ui/Button";
import { StatusLabel } from "../ui/StatusLabel";

export function SectionBand<Id extends string>({
  verdictLabel,
  sections,
  active,
  onJump,
  onAsk,
}: {
  verdictLabel: string | null;
  sections: Id[];
  active: Id | null;
  onJump: (id: Id) => void;
  onAsk: () => void;
}) {
  const { t } = useTranslation("pages");
  return (
    <>
      <nav
        aria-label={t("scorecard.sectionsNav")}
        data-sticky-band
        className="sticky top-[4.5rem] z-20 -mx-4 mb-8 hidden items-center gap-4 border-y border-dark-border bg-dark-bg/95 px-4 py-2 backdrop-blur md:-mx-8 md:flex md:px-8"
      >
        {verdictLabel && <StatusLabel tone="neutral" glyph={null} className="shrink-0">{verdictLabel}</StatusLabel>}
        <div className="flex min-w-0 items-center gap-1 overflow-x-auto">
          {sections.map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => onJump(id)}
              aria-current={active === id ? "true" : undefined}
              className={`shrink-0 rounded-md px-2.5 py-1 text-caption cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                active === id ? "bg-dark-elevated text-text-primary" : "text-text-muted hover:text-text-secondary"
              }`}
            >
              {t(`scorecard.moduleNav.${id.replace("module-", "")}`)}
            </button>
          ))}
        </div>
      </nav>

      <div
        data-sticky-band
        data-testid="phone-action-bar"
        className="fixed inset-x-0 bottom-0 z-30 flex items-center gap-3 border-t border-dark-border bg-dark-surface px-4 py-2.5 md:hidden"
        style={{ paddingBottom: "max(0.625rem, env(safe-area-inset-bottom))" }}
      >
        {verdictLabel && <StatusLabel tone="neutral" glyph={null} className="min-w-0">{verdictLabel}</StatusLabel>}
        <Button variant="primary" size="lg" className="ml-auto" onClick={onAsk}>
          {t("scorecard.header.ask")}
        </Button>
      </div>
    </>
  );
}
