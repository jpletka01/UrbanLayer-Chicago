import { Children, cloneElement, isValidElement, useCallback, useMemo, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getUploadUrl } from "../lib/api";
import type { CodeChunk, DataSource, Message } from "../lib/types";
import { useCopyButton } from "../lib/useCopyButton";
import { useTypewriter } from "../lib/useTypewriter";
import { CitationPill } from "./CitationPill";
import { DataPill } from "./DataPill";
import { DisclaimerBanner } from "./DisclaimerBanner";

interface Props {
  message: Message;
  streaming?: boolean;
  showDisclaimer?: boolean;
  onCitationClick?: (index: number) => void;
  onDataClick?: (source: DataSource) => void;
  codeChunks?: CodeChunk[];
  isSelected?: boolean;
  onSelect?: () => void;
}

export function MessageBubble({ message, streaming, showDisclaimer, onCitationClick, onDataClick, codeChunks = [], isSelected, onSelect }: Props) {
  const isUser = message.role === "user";
  const [hovered, setHovered] = useState(false);
  const { copied, copy } = useCopyButton(message.content);

  const displayedContent = useTypewriter(message.content, !!streaming);

  const processTextWithCitations = useCallback((text: string): ReactNode[] => {
    const parts = text.split(/(\[\d+\]|\[data:(?:crime|311|permits|violations|business)\])/g);
    return parts.map((part, i) => {
      const numMatch = part.match(/^\[(\d+)\]$/);
      if (numMatch) {
        const index = parseInt(numMatch[1], 10) - 1;
        if (index >= 0 && index < codeChunks.length) {
          return (
            <CitationPill
              key={`citation-${index}-${i}`}
              index={index}
              chunk={codeChunks[index]}
              onClick={onCitationClick}
            />
          );
        }
        // No matching chunk - suppress the citation marker entirely
        return null;
      }
      const dataMatch = part.match(/^\[data:(crime|311|permits|violations|business)\]$/);
      if (dataMatch) {
        const source = dataMatch[1] as DataSource;
        return <DataPill key={`data-${source}-${i}`} source={source} onClick={onDataClick} />;
      }
      return part;
    });
  }, [codeChunks, onCitationClick, onDataClick]);

  const renderChildrenWithCitations = useCallback((children: ReactNode): ReactNode => {
    return Children.map(children, (child, childIndex) => {
      if (typeof child === "string") {
        return processTextWithCitations(child);
      }
      if (isValidElement(child)) {
        const props = child.props as { children?: ReactNode };
        if (props.children) {
          return cloneElement(child, { key: `md-${childIndex}` }, renderChildrenWithCitations(props.children));
        }
      }
      return child;
    });
  }, [processTextWithCitations]);

  const markdownComponents = useMemo(() => ({
    p: ({ children }: { children?: ReactNode }) => (
      <p className="text-text-primary text-base leading-[1.7] mb-4 last:mb-0">
        {renderChildrenWithCitations(children)}
      </p>
    ),
    a: ({ children, href }: { children?: ReactNode; href?: string }) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-accent hover:text-accent-hover underline decoration-accent/30 hover:decoration-accent font-medium transition-colors"
      >
        {children}
      </a>
    ),
    ul: ({ children }: { children?: ReactNode }) => (
      <ul className="list-disc pl-5 mb-4 space-y-1.5 text-text-primary">{children}</ul>
    ),
    ol: ({ children }: { children?: ReactNode }) => (
      <ol className="list-decimal pl-5 mb-4 space-y-1.5 text-text-primary">{children}</ol>
    ),
    li: ({ children }: { children?: ReactNode }) => (
      <li className="text-base leading-relaxed">
        {renderChildrenWithCitations(children)}
      </li>
    ),
    strong: ({ children }: { children?: ReactNode }) => <strong className="font-semibold text-text-primary">{children}</strong>,
    em: ({ children }: { children?: ReactNode }) => <em className="italic text-text-primary">{children}</em>,
    pre: ({ children }: { children?: ReactNode }) => (
      <pre className="mb-4 rounded-lg bg-dark-elevated border border-dark-border p-4 overflow-x-auto text-sm font-mono leading-relaxed text-text-primary">
        {children}
      </pre>
    ),
    code: ({ children, className }: { children?: ReactNode; className?: string }) => {
      if (className) {
        return <code className="text-text-primary">{children}</code>;
      }
      return (
        <code className="px-1.5 py-0.5 rounded bg-dark-elevated text-accent text-sm font-mono">
          {children}
        </code>
      );
    },
    blockquote: ({ children }: { children?: ReactNode }) => (
      <blockquote className="border-l-2 border-accent/40 pl-4 mb-4 text-text-secondary italic">
        {children}
      </blockquote>
    ),
    hr: () => <hr className="border-dark-border my-6" />,
    h1: ({ children }: { children?: ReactNode }) => <h1 className="text-xl font-semibold text-text-primary mt-6 mb-3">{children}</h1>,
    h2: ({ children }: { children?: ReactNode }) => <h2 className="text-lg font-semibold text-text-primary mt-5 mb-2">{children}</h2>,
    h3: ({ children }: { children?: ReactNode }) => <h3 className="text-base font-semibold text-text-primary mt-4 mb-2">{children}</h3>,
    table: ({ children }: { children?: ReactNode }) => (
      <div className="overflow-x-auto mb-4 rounded-lg border border-dark-border">
        <table className="w-full text-sm">{children}</table>
      </div>
    ),
    thead: ({ children }: { children?: ReactNode }) => (
      <thead className="bg-dark-elevated text-text-primary">{children}</thead>
    ),
    tbody: ({ children }: { children?: ReactNode }) => (
      <tbody className="divide-y divide-dark-border">{children}</tbody>
    ),
    tr: ({ children }: { children?: ReactNode }) => (
      <tr className="hover:bg-white/[0.03] transition-colors">{children}</tr>
    ),
    th: ({ children }: { children?: ReactNode }) => (
      <th className="px-4 py-2.5 text-left font-semibold text-text-primary whitespace-nowrap">{children}</th>
    ),
    td: ({ children }: { children?: ReactNode }) => (
      <td className="px-4 py-2 text-text-secondary">{children}</td>
    ),
  }), [renderChildrenWithCitations]);

  if (isUser) {
    return (
      <div
        className="flex justify-end group"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <div
          className={`relative max-w-[85%] rounded-2xl px-4 py-3 bg-dark-bubble-user text-text-primary transition-all
            ${onSelect ? "cursor-pointer hover:ring-1 hover:ring-white/20" : ""}
            ${isSelected ? "ring-1 ring-accent/40" : ""}`}
          onClick={onSelect}
          title={onSelect ? "Click to view this question's data" : undefined}
        >
          {hovered && (
            <button
              onClick={(e) => { e.stopPropagation(); copy(); }}
              className="absolute -left-10 top-1/2 -translate-y-1/2 p-1.5 rounded-lg
                         bg-dark-surface/80 border border-dark-border
                         text-text-muted hover:text-text-primary hover:bg-dark-elevated
                         transition-all"
              title="Copy message"
            >
              {copied ? (
                <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              )}
            </button>
          )}
          <p className="text-base leading-relaxed whitespace-pre-wrap">{message.content}</p>
          {message.attachments && message.attachments.length > 0 && (
            <div className="flex gap-2 mt-2">
              {message.attachments.map((att) => (
                <button
                  key={att.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    window.open(getUploadUrl(att.id), "_blank");
                  }}
                  className="w-16 h-16 rounded-lg overflow-hidden border border-dark-border hover:border-accent/50 transition-colors shrink-0"
                  title={att.filename}
                >
                  {att.mime_type?.startsWith("image/") ? (
                    <img src={getUploadUrl(att.id)} alt={att.filename} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full bg-dark-elevated flex flex-col items-center justify-center gap-0.5">
                      <svg className="w-5 h-5 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                      </svg>
                      <span className="text-[8px] text-text-muted">PDF</span>
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex justify-start group"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="relative max-w-[85%] rounded-2xl px-4 py-3 bg-dark-bubble">
        {hovered && !streaming && displayedContent && (
          <button
            onClick={copy}
            className="absolute -right-10 top-3 p-1.5 rounded-lg
                       bg-dark-surface/80 border border-dark-border
                       text-text-muted hover:text-text-primary hover:bg-dark-elevated
                       transition-all"
            title="Copy message"
          >
            {copied ? (
              <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            )}
          </button>
        )}
        <div className="flex items-start gap-3">
          <div className="w-6 h-6 rounded-full bg-accent/20 flex items-center justify-center shrink-0">
            <svg className="w-3.5 h-3.5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            {displayedContent ? (
              <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                  {displayedContent}
                </ReactMarkdown>
                {streaming && (
                  <span className="inline-block w-0.5 h-5 bg-accent animate-blink align-text-bottom ml-0.5" />
                )}
              </div>
            ) : streaming ? (
              <div className="flex items-center gap-2.5">
                <div className="flex gap-1 items-end">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent animate-dot-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-accent animate-dot-bounce" style={{ animationDelay: "200ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-accent animate-dot-bounce" style={{ animationDelay: "400ms" }} />
                </div>
                <span className="text-sm font-medium animate-text-glow">Thinking</span>
              </div>
            ) : null}
            {showDisclaimer && <DisclaimerBanner />}
          </div>
        </div>
      </div>
    </div>
  );
}
