import { Children, cloneElement, isValidElement, useCallback, useMemo, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
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
}

export function MessageBubble({ message, streaming, showDisclaimer, onCitationClick, onDataClick, codeChunks = [] }: Props) {
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
    code: ({ children }: { children?: ReactNode }) => (
      <code className="px-1.5 py-0.5 rounded bg-dark-elevated text-accent text-sm font-mono">
        {children}
      </code>
    ),
    h1: ({ children }: { children?: ReactNode }) => <h1 className="text-xl font-semibold text-text-primary mt-6 mb-3">{children}</h1>,
    h2: ({ children }: { children?: ReactNode }) => <h2 className="text-lg font-semibold text-text-primary mt-5 mb-2">{children}</h2>,
    h3: ({ children }: { children?: ReactNode }) => <h3 className="text-base font-semibold text-text-primary mt-4 mb-2">{children}</h3>,
  }), [renderChildrenWithCitations]);

  if (isUser) {
    return (
      <div
        className="flex justify-end group"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <div className="relative max-w-[85%] rounded-2xl px-4 py-3 bg-dark-bubble-user text-text-primary">
          {hovered && (
            <button
              onClick={copy}
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
                <ReactMarkdown components={markdownComponents}>
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
