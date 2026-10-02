// "See the source" for a Profile standard: the exact Municipal Code subsection the
// number comes from, the table it cites, and how current the code text is. The code is
// a snapshot (the indexed export is current through a Council Journal date), so the
// viewer says so rather than letting the text read as live law.
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { fetchCodeSubsection, type CodeSubsection } from "../../lib/api";
import { parseCodeTable } from "../../lib/codeTable";
import { Modal } from "../ui/Modal";

function CodeTable({ text }: { text: string }) {
  const parsed = parseCodeTable(text);
  if (!parsed) return <pre className="text-caption text-text-secondary whitespace-pre-wrap">{text}</pre>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-caption border-collapse">
        <thead>
          <tr>
            {parsed.columns.map((c) => (
              <th key={c} className="text-left font-medium text-text-muted border-b border-border-subtle px-2 py-1 align-bottom">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {parsed.rows.map((r, i) => (
            <tr key={i} className="border-b border-border-subtle/50 last:border-b-0">
              {r.map((cell, j) => (
                <td key={j} className="px-2 py-1 text-text-primary align-top">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CodeSourceModal({ sectionId, onClose }: { sectionId: string; onClose: () => void }) {
  const { t } = useTranslation("pages");
  const [data, setData] = useState<CodeSubsection | null | undefined>(undefined);

  useEffect(() => {
    let live = true;
    fetchCodeSubsection(sectionId).then((d) => live && setData(d));
    return () => {
      live = false;
    };
  }, [sectionId]);

  return (
    <Modal onClose={onClose} size="lg" title={`§ ${sectionId}${data ? ` — ${data.heading}` : ""}`}
      description={data?.article_title}>
      <div className="space-y-4" data-testid="code-source">
        {data === undefined && <p className="text-caption text-text-muted">{t("scorecard.codeSource.loading")}</p>}
        {data === null && <p className="text-caption text-text-muted">{t("scorecard.codeSource.unavailable")}</p>}
        {data && (
          <>
            <div className="space-y-2">
              {data.paragraphs.map((p, i) => (
                <p key={i} className="text-caption text-text-secondary leading-relaxed">{p}</p>
              ))}
            </div>
            {data.tables.map((tbl, i) => (
              <CodeTable key={i} text={tbl} />
            ))}
            {data.current_through && (
              <p className="text-caption text-text-muted border-t border-border-subtle pt-3" data-testid="code-vintage">
                {t("scorecard.codeSource.vintage", { date: data.current_through })}
              </p>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}
