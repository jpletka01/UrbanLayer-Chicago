// The full chat page's message box (brief "Chat"): a paperclip on the left (where uploads are allowed), dictation
// beside a round arrow that sends, Enter sends too. On a new conversation one example question types itself in the
// empty box and gives way to the next; clicking the box (or typing) clears it and leaves no placeholder behind. With reduced motion the first example
// just sits there.
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ArrowUp, Mic, MicOff, Paperclip, Square, X } from "lucide-react";
import type { PendingAttachment } from "../../components/ChatInput";
import { STROKE } from "../icons";
import { useDictation } from "./useDictation";

function prefersReducedMotion(): boolean {
  try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; }
}

/** One example at a time, typed a letter at a time, held, then erased. */
function useTypedExample(examples: string[], on: boolean): string {
  const [text, setText] = useState(examples[0] ?? "");
  useEffect(() => {
    if (!on || examples.length === 0 || prefersReducedMotion()) { setText(examples[0] ?? ""); return; }
    let n = 0, i = 0, erasing = false, timer = 0;
    const tick = () => {
      const s = examples[n];
      if (!erasing) {
        i += 1;
        setText(s.slice(0, i));
        if (i >= s.length) { erasing = true; timer = window.setTimeout(tick, 2600); return; }
        timer = window.setTimeout(tick, 45);
      } else {
        i -= 2;
        setText(s.slice(0, Math.max(0, i)));
        if (i <= 0) { erasing = false; i = 0; n = (n + 1) % examples.length; timer = window.setTimeout(tick, 500); return; }
        timer = window.setTimeout(tick, 18);
      }
    };
    setText("");
    timer = window.setTimeout(tick, 700);
    return () => window.clearTimeout(timer);
  }, [examples, on]);
  return text;
}

export function Composer({
  value,
  onChange,
  onSend,
  onStop,
  streaming,
  disabled,
  placeholder,
  examples,
  above,
  onAttach,
  attachments = [],
  onRemoveAttachment,
  autoFocus,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop?: () => void;
  streaming: boolean;
  /** At the conversation's limit: the box stays visible but can't send. */
  disabled?: boolean;
  placeholder: string;
  /** Examples that type themselves while the box is empty (a new conversation only). */
  examples?: string[];
  /** A line above the box (what the analyst is asked about). */
  above?: ReactNode;
  onAttach?: (files: File[]) => void;
  attachments?: PendingAttachment[];
  onRemoveAttachment?: (i: number) => void;
  autoFocus?: boolean;
}) {
  const { t, i18n } = useTranslation("next");
  const id = useId();
  const box = useRef<HTMLTextAreaElement | null>(null);
  const file = useRef<HTMLInputElement | null>(null);
  const [focused, setFocused] = useState(false);
  // No example while the box can't be used (the allowance is spent): a disabled box can't take focus, so an example
  // would keep typing over it and read as an input that ignores the visitor (owner, 2026-11-12).
  const typed = useTypedExample(examples ?? [], !!examples?.length && !focused && !value && !disabled);
  const base = useRef("");
  const dictation = useDictation(i18n.language, (spoken) => onChange(base.current ? `${base.current} ${spoken}` : spoken));

  // The box grows with its text up to about six lines.
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
    // Scroll only once the text is past the six-line cap; below it a sub-pixel gap let one line scroll.
    el.style.overflowY = el.scrollHeight > 168 ? "auto" : "hidden";
  }, [value]);

  const showExample = !!examples?.length && !focused && !value && !disabled;
  const canSend = !disabled && !streaming && !!value.trim();

  return (
    <div className="flex flex-col gap-1.5">
      {above}
      {attachments.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label={t("chat.attachments")}>
          {attachments.map((a, i) => (
            <li key={i} className="flex items-center gap-1.5 rounded-lg bg-nx-block px-2 py-1 text-caption">
              <Paperclip aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
              <span className="max-w-[12rem] truncate">{a.file.name}</span>
              <button type="button" onClick={() => onRemoveAttachment?.(i)} aria-label={t("chat.removeAttachment", { name: a.file.name })} className="grid h-5 w-5 place-items-center rounded hover:bg-nx-ink/10 touch-icon">
                <X aria-hidden className="h-3 w-3" strokeWidth={STROKE} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        className="nx-ai-edge rounded-[22px] focus-within:shadow-[0_0_0_3px_rgb(var(--nx-ai-a)/0.6)]"
        onSubmit={(e) => { e.preventDefault(); if (canSend) onSend(); }}
      >
        <div className="flex items-end gap-1 rounded-[21px] bg-nx-page py-1.5 pl-1.5 pr-1.5">
          {onAttach && (
            <>
              <button
                type="button"
                onClick={() => file.current?.click()}
                disabled={disabled || attachments.length >= 3}
                aria-label={t("chat.attach")}
                title={t("chat.attach")}
                className="grid h-10 w-10 shrink-0 place-items-center rounded-full hover:bg-nx-ink/5 disabled:opacity-40 touch-icon"
              >
                <Paperclip aria-hidden className="h-5 w-5" strokeWidth={STROKE} />
              </button>
              <input
                ref={file}
                type="file"
                accept="image/*,application/pdf"
                multiple
                className="hidden"
                onChange={(e) => { const f = Array.from(e.target.files ?? []); if (f.length) onAttach(f); e.target.value = ""; }}
              />
            </>
          )}
          <div className="relative min-w-0 flex-1 self-center">
            <label htmlFor={`${id}-box`} className="sr-only">{placeholder}</label>
            <textarea
              id={`${id}-box`}
              ref={box}
              rows={1}
              value={value}
              autoFocus={autoFocus}
              disabled={disabled}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  if (canSend) onSend();
                }
              }}
              // On a new chat the examples stand in for a placeholder: clicking leaves the box empty with the cursor,
              // not a second sentence that stays until the first letter (owner, 2026-11-12).
              placeholder={examples?.length && !disabled ? "" : placeholder}
              className={`block w-full resize-none bg-transparent px-2 py-2 text-body text-nx-ink placeholder:text-nx-ink/[0.64] focus:outline-none focus-visible:outline-none disabled:opacity-50 ${onAttach ? "" : "pl-3"}`}
              data-testid="chat-box"
            />
            {showExample && (
              <span aria-hidden className={`pointer-events-none absolute inset-y-0 left-0 flex items-center truncate px-2 text-body nx-muted ${onAttach ? "" : "pl-3"}`} data-testid="chat-example">
                {typed}
                <span className="ml-px inline-block h-[1.1em] w-px bg-current motion-safe:animate-pulse" />
              </span>
            )}
          </div>
          {dictation.supported && (
            <button
              type="button"
              onClick={() => {
                if (dictation.listening) { dictation.stop(); return; }
                base.current = value.trim();
                dictation.start();
              }}
              disabled={disabled || streaming}
              aria-pressed={dictation.listening}
              aria-label={dictation.listening ? t("chat.dictateStop") : t("chat.dictate")}
              title={dictation.listening ? t("chat.dictateStop") : t("chat.dictate")}
              className={`grid h-10 w-10 shrink-0 place-items-center rounded-full disabled:opacity-40 touch-icon ${dictation.listening ? "bg-nx-pill-red-bg text-nx-pill-red" : "hover:bg-nx-ink/5"}`}
              data-testid="chat-dictate"
            >
              {dictation.failed ? <MicOff aria-hidden className="h-5 w-5" strokeWidth={STROKE} /> : <Mic aria-hidden className="h-5 w-5" strokeWidth={STROKE} />}
            </button>
          )}
          {streaming && onStop ? (
            <button type="button" onClick={onStop} aria-label={t("chat.stop")} title={t("chat.stop")} className="nx-ai-send grid h-10 w-10 shrink-0 place-items-center rounded-full touch-icon">
              <Square aria-hidden className="h-4 w-4" strokeWidth={2} />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSend}
              aria-label={t("chat.send")}
              title={t("chat.send")}
              className="nx-ai-send grid h-10 w-10 shrink-0 place-items-center rounded-full disabled:opacity-50 touch-icon"
              data-testid="chat-send"
            >
              <ArrowUp aria-hidden className="h-5 w-5" strokeWidth={2.2} />
            </button>
          )}
        </div>
      </form>
      {dictation.failed && <p className="text-caption nx-muted" role="status">{t("chat.dictateFailed")}</p>}
    </div>
  );
}
