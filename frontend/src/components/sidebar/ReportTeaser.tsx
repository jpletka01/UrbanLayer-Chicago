import { Link } from "react-router-dom";
import { track } from "../../lib/tracking";

const DocumentIcon = (
  <svg className="w-3 h-3 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
  </svg>
);

export function ReportTeaser({ text, href }: { text: string; href?: string | null }) {
  if (href) {
    return (
      <Link
        to={href}
        onClick={() => track("scorecard_bridge_click", { source: "teaser" })}
        className="mt-3 pt-2 border-t border-dashed border-dark-border/50 flex items-center gap-1.5 text-micro text-text-secondary hover:text-accent transition-colors"
      >
        {DocumentIcon}
        {text} →
      </Link>
    );
  }
  return (
    <div className="mt-3 pt-2 border-t border-dashed border-dark-border/50 flex items-center gap-1.5 text-micro text-text-muted">
      {DocumentIcon}
      {text}
    </div>
  );
}
