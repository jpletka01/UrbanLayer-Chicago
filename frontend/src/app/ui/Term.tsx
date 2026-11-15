// A label that defines itself (decision Item 99): the words stay plain on the page; a small Info icon beside them
// opens the definition. On a desktop it is a popover (hover previews, a click pins); on a phone a floating popover
// is cramped and its icon is a poor touch target, so the same icon (with a 44 px hit area) opens a short bottom
// sheet in body-size text that slides up and back down. Reading comes first (owner: questions cost money, so
// definitions should be enough on their own); "Ask the analyst" is a quiet secondary link that opens the Ask drawer
// with a question about this lot written in the box, never sent.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { Info, X } from "lucide-react";
import { Toggletip } from "../../components/ui/Toggletip";
import { useAskHandoff } from "../ask/askContext";
import { ICON, STROKE } from "../icons";

export function Term({ label, definition, question, children }: {
  /** The term as the visitor reads it ("Rent nearby"). */
  label: string;
  definition: ReactNode;
  /** The question "Ask the analyst" writes, with the address already filled in by the caller. */
  question?: string;
  /** What shows on the page; the label when omitted. */
  children?: ReactNode;
}) {
  const { t } = useTranslation("next");
  return (
    <span className="inline-flex items-center gap-1">
      {children ?? label}
      <span className="hidden md:inline-flex">
        <Toggletip label={t("term.what", { term: label })}>
          <span className="flex flex-col gap-2" data-term={label}>
            <span>{definition}</span>
            <AskLink question={question} />
          </span>
        </Toggletip>
      </span>
      <TermSheet label={label} definition={definition} question={question} />
    </span>
  );
}

function AskLink({ question, onDone }: { question?: string; onDone?: () => void }) {
  const { t } = useTranslation("next");
  const ask = useAskHandoff();
  const AskIcon = ICON.ask;
  if (!ask || !question) return null;
  return (
    <button
      type="button"
      disabled={!ask.ready}
      onClick={() => { onDone?.(); ask.open(question); }}
      className="inline-flex items-center gap-1.5 self-start text-caption nx-muted underline underline-offset-2 hover:text-nx-ink disabled:no-underline disabled:opacity-60 touch-target"
      data-testid="term-ask"
    >
      <AskIcon aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
      {ask.ready ? t("term.ask") : t("term.askLater")}
    </button>
  );
}

/** The phone's definition: a bottom sheet that slides up, and back down before it closes. */
function TermSheet({ label, definition, question }: { label: string; definition: ReactNode; question?: string }) {
  const { t } = useTranslation("next");
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [entered, setEntered] = useState(false);
  const timer = useRef<number | null>(null);
  useEffect(() => {
    if (!mounted || entered || !open) return;
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setEntered(true)));
    return () => cancelAnimationFrame(id);
  }, [mounted, entered, open]);
  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current); }, []);
  const show = () => { if (timer.current) window.clearTimeout(timer.current); setOpen(true); setMounted(true); };
  const hide = () => {
    setOpen(false);
    timer.current = window.setTimeout(() => { setMounted(false); setEntered(false); }, 200);
  };
  const shown = open && entered;

  return (
    <Dialog.Root open={mounted} onOpenChange={(o) => (o ? show() : hide())}>
      <Dialog.Trigger
        className="inline-flex items-center rounded px-0.5 nx-muted hover:text-nx-ink md:hidden touch-hit"
        aria-label={t("term.what", { term: label })}
      >
        <Info aria-hidden className="h-3.5 w-3.5" strokeWidth={2} />
      </Dialog.Trigger>
      <Dialog.Portal>
        <div className="ui-next">
          <Dialog.Overlay
            className={`fixed inset-0 z-[70] bg-black/40 transition-opacity duration-200 ${shown ? "opacity-100" : "opacity-0"}`}
          />
          <Dialog.Content
            className={`fixed inset-x-0 bottom-0 z-[71] flex max-h-[70dvh] flex-col gap-3 overflow-y-auto rounded-t-2xl bg-nx-page p-5 pb-[calc(env(safe-area-inset-bottom)+1.25rem)] text-body text-nx-ink shadow-[0_-8px_32px_rgb(0_0_0/0.2)] transition-transform duration-200 ease-out focus:outline-none ${shown ? "translate-y-0" : "translate-y-full"}`}
            data-testid="term-sheet"
          >
            <span aria-hidden className="mx-auto mb-1 h-1 w-10 rounded-full bg-nx-ink/20" />
            <div className="flex items-start justify-between gap-3">
              <Dialog.Title className="font-semibold">{label}</Dialog.Title>
              <Dialog.Close className="-mr-1 -mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon" aria-label={t("term.close")}>
                <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
              </Dialog.Close>
            </div>
            <Dialog.Description asChild>
              <div className="leading-relaxed">{definition}</div>
            </Dialog.Description>
            <AskLink question={question} onDone={hide} />
          </Dialog.Content>
        </div>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
