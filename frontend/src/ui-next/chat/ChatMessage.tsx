// One turn of the new chat (owner review 2026-11-12: the chat still wore the old UI). The question is a quiet bubble on
// the right; the answer is plain text on the page, as in the evidence panel. A citation is a small chip in its source's
// color (code purple, this lot green, around the lot blue — the Sources list's colors); hovering or focusing it shows
// a card with the exact passage the answer used, and a click opens that source in the panel.
import { Children, cloneElement, isValidElement, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy } from "lucide-react";
import { stripHeader } from "../../lib/codeRefs";
import type { DataSource, Message } from "../../lib/types";
import { useCopyButton } from "../../lib/useCopyButton";
import { useTypewriter } from "../../lib/useTypewriter";
import { getUploadUrl } from "../../lib/api";
import { STROKE } from "../icons";
import { groupOf, numberForData, sourcesFor, type SourceGroup, type SourceItem } from "./evidenceModel";

const CITE = /(\[\d+\]|\[data:(?:crime|311|permits|violations|business|vacant_buildings|food_inspections)\])/g;
const DOT: Record<SourceGroup, string> = {
  code: "bg-nx-pill-purple-bg text-nx-pill-purple",
  lot: "bg-nx-pill-green-bg text-nx-pill-green",
  area: "bg-nx-pill-blue-bg text-nx-pill-blue",
};

interface Props {
  message: Message;
  streaming?: boolean;
  /** Opens source n in the evidence panel. */
  onOpenSource?: (n: number) => void;
  /** Under the answer: the lot / map / sources chips. */
  footer?: ReactNode;
  /** Beside the copy button: when it was answered, and what changed since. */
  meta?: ReactNode;
}

export function ChatMessage({ message, streaming = false, onOpenSource, footer, meta }: Props) {
  const { t } = useTranslation("next");
  const { copied, copy } = useCopyButton(message.content);
  const shown = useTypewriter(message.content, streaming);
  const items = useMemo(() => (streaming ? [] : sourcesFor(message)), [message, streaming]);

  if (message.role === "user") {
    return (
      <div className="group flex justify-end" data-testid="chat-question">
        <div className="max-w-[85%] rounded-3xl bg-nx-block px-4 py-2.5">
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
          {(message.attachments?.length ?? 0) > 0 && (
            <div className="mt-2 flex gap-2">
              {message.attachments!.map((a) => (
                <a key={a.id} href={getUploadUrl(a.id)} target="_blank" rel="noopener noreferrer" title={a.filename} className="h-14 w-14 overflow-hidden rounded-xl ring-1 ring-nx-ink/10">
                  {a.mime_type?.startsWith("image/") ? <img src={getUploadUrl(a.id)} alt={a.filename} className="h-full w-full object-cover" /> : <span className="grid h-full w-full place-items-center text-caption nx-muted">PDF</span>}
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  const cite = (text: string): ReactNode[] => text.split(CITE).map((part, i) => {
    const num = /^\[(\d+)\]$/.exec(part);
    const data = /^\[data:([a-z_0-9]+)\]$/.exec(part);
    if (!num && !data) return part;
    if (streaming) return null; // numbers settle once the answer is in
    const n = num ? Number(num[1]) : numberForData(items, data![1] as DataSource);
    const it = n != null ? items.find((x) => x.n === n) : undefined;
    if (!it) return null;
    return <Cite key={`c${i}`} item={it} label={num ? undefined : t(`chat.cite.${data![1]}`)} onOpen={onOpenSource} />;
  });
  const walk = (children: ReactNode): ReactNode => Children.map(children, (child, k) => {
    if (typeof child === "string") return cite(child);
    if (isValidElement(child)) {
      const kids = (child.props as { children?: ReactNode }).children;
      return kids ? cloneElement(child, { key: `m${k}` }, walk(kids)) : child;
    }
    return child;
  });
  type C = { children?: ReactNode };
  const md = {
    p: ({ children }: C) => <p className="mb-4 leading-[1.7] last:mb-0">{walk(children)}</p>,
    li: ({ children }: C) => <li className="leading-relaxed">{walk(children)}</li>,
    td: ({ children }: C) => <td className="px-3 py-2 align-top">{walk(children)}</td>,
    ul: ({ children }: C) => <ul className="mb-4 list-disc space-y-1.5 pl-5">{children}</ul>,
    ol: ({ children }: C) => <ol className="mb-4 list-decimal space-y-1.5 pl-5">{children}</ol>,
    a: ({ children, href }: C & { href?: string }) => <a href={href} target="_blank" rel="noopener noreferrer" className="font-medium underline underline-offset-2 hover:no-underline">{children}</a>,
    strong: ({ children }: C) => <strong className="font-semibold">{children}</strong>,
    h1: ({ children }: C) => <h3 className="mb-2 mt-5 text-[1.125rem] font-semibold">{children}</h3>,
    h2: ({ children }: C) => <h3 className="mb-2 mt-5 text-[1.0625rem] font-semibold">{children}</h3>,
    h3: ({ children }: C) => <h4 className="mb-2 mt-4 font-semibold">{children}</h4>,
    hr: () => <hr className="my-5 border-nx-ink/10" />,
    blockquote: ({ children }: C) => <blockquote className="mb-4 border-l-2 border-nx-ink/20 pl-4 nx-muted">{children}</blockquote>,
    code: ({ children }: C) => <code className="rounded bg-nx-block px-1 py-0.5 text-[0.875em]">{children}</code>,
    pre: ({ children }: C) => <pre className="mb-4 overflow-x-auto rounded-xl bg-nx-block p-3 text-caption">{children}</pre>,
    table: ({ children }: C) => <div className="mb-4 overflow-x-auto rounded-xl ring-1 ring-nx-ink/10"><table className="w-full text-caption">{children}</table></div>,
    thead: ({ children }: C) => <thead className="bg-nx-block text-left">{children}</thead>,
    tbody: ({ children }: C) => <tbody className="divide-y divide-nx-ink/10">{children}</tbody>,
    th: ({ children }: C) => <th className="whitespace-nowrap px-3 py-2 font-semibold">{children}</th>,
  };

  return (
    <div className="group flex flex-col gap-2" data-testid="chat-answer">
      {shown && (
        <div className="min-w-0 text-[1rem]">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={md}>{shown}</ReactMarkdown>
          {streaming && <span aria-hidden className="ml-0.5 inline-block h-5 w-0.5 animate-blink bg-nx-ink align-text-bottom" />}
        </div>
      )}
      {!streaming && shown && footer}
      {!streaming && shown && (
        <div className="flex items-start gap-2">
          <button type="button" onClick={copy} className="inline-flex items-center gap-1 rounded-lg px-1.5 py-1 text-caption nx-muted hover:bg-nx-ink/5 touch-target" aria-label={copied ? t("chat.cite.copied") : t("chat.cite.copy")} data-testid="chat-copy">
            {copied ? <Check aria-hidden className="h-4 w-4" strokeWidth={STROKE} /> : <Copy aria-hidden className="h-4 w-4" strokeWidth={STROKE} />}
          </button>
          {meta && <div className="min-w-0 flex-1 pt-1">{meta}</div>}
        </div>
      )}
    </div>
  );
}

/** A citation: number in its source's color plus a short name; a card on hover or focus, the source on click. */
function Cite({ item, label, onOpen }: { item: SourceItem; label?: string; onOpen?: (n: number) => void }) {
  const { t } = useTranslation("next");
  const [show, setShow] = useState(false);
  const group = groupOf(item.kind);
  const name = item.kind === "code" ? `§ ${item.chunk.section}` : (label ?? "");
  return (
    <span className="relative inline-block align-baseline">
      <button
        type="button"
        onClick={() => onOpen?.(item.n)}
        onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}
        onFocus={() => setShow(true)} onBlur={() => setShow(false)}
        aria-label={t("chat.cite.open", { name, n: item.n })}
        className="mx-0.5 inline-flex h-6 items-center gap-1 rounded-full bg-nx-page py-0 pl-0.5 pr-2 align-[0.1em] text-[0.75rem] font-medium ring-1 ring-nx-ink/15 hover:bg-nx-block"
        data-testid="cite" data-group={group}
      >
        <span className={`grid h-5 min-w-5 place-items-center rounded-full px-1 text-[0.6875rem] font-semibold ${DOT[group]}`}>{item.n}</span>
        <span className="whitespace-nowrap">{name}</span>
      </button>
      {show && <CiteCard item={item} name={name} group={group} />}
    </span>
  );
}

function CiteCard({ item, name, group }: { item: SourceItem; name: string; group: SourceGroup }) {
  const { t } = useTranslation("next");
  const anchor = useRef<HTMLSpanElement>(null);
  const card = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  useLayoutEffect(() => {
    const trigger = anchor.current?.parentElement;
    const el = card.current;
    if (!trigger || !el) return;
    const r = trigger.getBoundingClientRect();
    const left = Math.max(8, Math.min(r.left + r.width / 2 - el.offsetWidth / 2, window.innerWidth - el.offsetWidth - 8));
    let top = r.top - el.offsetHeight - 8;
    if (top < 8) top = r.bottom + 8;
    setPos({ left, top });
  }, []);
  const title = item.kind === "code" ? (item.chunk.section_title ?? "") : t(`chat.src.${item.kind}`, { area: "" });
  let body: ReactNode = null;
  if (item.kind === "code") {
    const text = item.chunk.text ?? "";
    body = item.passage
      ? <mark className="rounded bg-nx-pill-yellow-bg px-0.5 text-nx-ink">{trim(text.slice(item.passage[0], item.passage[1]), 260)}</mark>
      : <span className="nx-muted">{trim(stripHeader(text), 200)}</span>;
  }
  return (
    <>
      <span ref={anchor} style={{ position: "absolute", width: 0, height: 0, overflow: "hidden" }} />
      {createPortal(
        <div className="ui-next">
          <div ref={card} role="tooltip" className="pointer-events-none fixed z-[80] flex w-80 flex-col gap-1.5 rounded-2xl bg-nx-page p-3 text-caption text-nx-ink shadow-[0_8px_30px_rgb(0_0_0/0.18)] ring-1 ring-nx-ink/10" style={pos ? { left: pos.left, top: pos.top } : { left: 0, top: 0, opacity: 0 }} data-testid="cite-card">
            <span className="flex items-center gap-2">
              <span className={`grid h-5 min-w-5 place-items-center rounded-full px-1 text-[0.6875rem] font-semibold ${DOT[group]}`}>{item.n}</span>
              <strong className="truncate">{item.kind === "code" ? name : title}</strong>
            </span>
            {item.kind === "code" && title && <span className="nx-muted">{title}</span>}
            {body && <span className="leading-relaxed">{body}</span>}
            <span className="nx-muted">{t("chat.cite.click")}</span>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}

function trim(s: string, max: number): string {
  const one = s.replace(/\s+/g, " ").trim();
  return one.length > max ? `${one.slice(0, max - 1).trimEnd()}…` : one;
}
