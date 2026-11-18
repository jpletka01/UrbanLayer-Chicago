// Suggest a correction (decision Item 129 §1, PR 3): a pencil beside the lot's × (the laptop card and the phone's lot
// sheet) opens one question, "What's wrong with this building?", answered by tapping chips (several allowed), a typed
// story count, a direction for the floor area and an optional note. It takes the focus the way the app's other dialogs
// do: a centered dialog on a laptop, a sheet over the whole screen on a phone (drag down past 120 px or × to close).
// Sent = a toast in the page's corner and the pencil turns into a check. Nothing is applied: a person reviews every
// report (PR 4), and an accepted one only ever replaces the footprint × stories estimate.
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { Check, PencilLine, X } from "lucide-react";
import { sendLotCorrection, type LotCorrectionBody, type LotCorrectionKind } from "../../lib/api";
import { STROKE } from "../icons";
import { showToast } from "../ui/Toast";

// ---------------------------------------------------------------- the form's rules (pure)

export type Chip = LotCorrectionKind;
export interface CorrectionForm { chips: Chip[]; stories: string; area: "high" | "low" | null; note: string }
export const EMPTY_FORM: CorrectionForm = { chips: [], stories: "", area: null, note: "" };
export const NOTE_MAX = 280;

/** Tap a chip: several may be on, but "no building now" makes stories and floor area moot, and either clears it. */
export function toggleChip(f: CorrectionForm, c: Chip): CorrectionForm {
  let chips = f.chips.includes(c) ? f.chips.filter((x) => x !== c) : [...f.chips, c];
  if (c === "gone" && chips.includes("gone")) chips = chips.filter((x) => x !== "stories" && x !== "area");
  if ((c === "stories" || c === "area") && chips.includes(c)) chips = chips.filter((x) => x !== "gone");
  return { ...f, chips };
}

/** Send is on once something is picked, with a story count typed if Stories is, and a direction if Floor area is. */
export function formReady(f: CorrectionForm): boolean {
  const n = Number(f.stories);
  return f.chips.length > 0
    && (!f.chips.includes("stories") || (/^\d{1,3}$/.test(f.stories) && n >= 1 && n <= 150))
    && (!f.chips.includes("area") || f.area != null);
}

/** What the server is sent: only the fields the picked chips need (it refuses a count without Stories). */
export function toBody(pin10: string, f: CorrectionForm): LotCorrectionBody {
  const note = f.note.trim().slice(0, NOTE_MAX);
  return {
    pin: pin10,
    kinds: f.chips,
    ...(f.chips.includes("stories") ? { stories: Number(f.stories) } : {}),
    ...(f.chips.includes("area") && f.area ? { area_dir: f.area } : {}),
    ...(note ? { note } : {}),
  };
}

/** The chips this lot gets: a lot we show empty asks "There's a building" instead of stories, floor area and "no
 * building now"; the condo chip says whichever contradicts what we show. Both building-presence chips are the kind
 * `gone`, both condo chips `condo`: the server's snapshot of the card says which way the report points. */
export function chipsFor(lot: { hasBuilding: boolean; condo: boolean }): Array<[Chip, string]> {
  return [
    ...(lot.hasBuilding
      ? [["stories", "chips.stories"], ["area", "chips.area"], ["gone", "chips.gone"]] as Array<[Chip, string]>
      : [["gone", "chips.there"]] as Array<[Chip, string]>),
    ["condo", lot.condo ? "chips.notCondo" : "chips.isCondo"],
    ["other", "chips.other"],
  ];
}

// ---------------------------------------------------------------- lots sent from this browser (this session)

const SENT_KEY = "urbanlayer-next-corrections-sent";
const sentListeners = new Set<() => void>();
let sentCache: string | null = null;

function readSent(): string {
  if (sentCache != null) return sentCache;
  try { sentCache = sessionStorage.getItem(SENT_KEY) ?? ""; } catch { sentCache = ""; }
  return sentCache;
}

function markSent(pin10: string) {
  const set = new Set(readSent().split(",").filter(Boolean));
  set.add(pin10);
  sentCache = [...set].join(",");
  try { sessionStorage.setItem(SENT_KEY, sentCache); } catch { /* private window: this page view only */ }
  sentListeners.forEach((l) => l());
}

function useSent(pin10: string): boolean {
  const raw = useSyncExternalStore(
    (l) => { sentListeners.add(l); return () => { sentListeners.delete(l); }; },
    readSent, () => "",
  );
  return raw.split(",").includes(pin10);
}

/** Tests only: forget what this browser sent. */
export function resetCorrectionsSent() {
  sentCache = null;
  try { sessionStorage.removeItem(SENT_KEY); } catch { /* nothing kept */ }
}

// ---------------------------------------------------------------- the pieces

const ICON_BTN = "grid place-items-center rounded-lg hover:bg-nx-ink/5";
const BTN_PRIMARY = "inline-flex items-center justify-center gap-2 rounded-full bg-nx-primary px-5 py-2 font-semibold text-nx-primary-fg disabled:opacity-40 touch-target";
const BTN_SECONDARY = "inline-flex items-center justify-center gap-2 rounded-full px-4 py-2 font-medium ring-1 ring-nx-ink/15 hover:bg-nx-ink/5 touch-target";

/** An icon with its name as a tooltip on hover and keyboard focus (the name is also its accessible name). */
function Tip({ label }: { label: string }) {
  return (
    <span role="tooltip" aria-hidden
      className="pointer-events-none absolute right-0 top-full z-30 mt-1 hidden whitespace-nowrap rounded-md bg-nx-ink px-2 py-1 text-[11px] font-normal text-nx-on-ink group-hover:block group-focus-within:block">
      {label}
    </span>
  );
}

function FormBody({ form, setForm, lot, big }: {
  form: CorrectionForm; setForm: (f: (p: CorrectionForm) => CorrectionForm) => void; lot: { hasBuilding: boolean; condo: boolean }; big: boolean;
}) {
  const { t } = useTranslation("next");
  const storiesRef = useRef<HTMLInputElement>(null);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const last = form.chips[form.chips.length - 1];
  // Picking Stories puts the cursor in its field (a numeric keyboard on a phone); Other, in the note.
  useEffect(() => {
    if (last === "stories") storiesRef.current?.focus({ preventScroll: true });
    if (last === "other") noteRef.current?.focus({ preventScroll: true });
  }, [last]);
  const on = (c: Chip) => form.chips.includes(c);
  const chipH = big ? "h-10 px-4" : "h-9 px-3.5";
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("discovery.correction.question")} data-testid="correction-chips">
        {chipsFor(lot).map(([c, key]) => (
          <button key={c} type="button" aria-pressed={on(c)} onClick={() => setForm((f) => toggleChip(f, c))} data-chip={c}
            className={`inline-flex items-center gap-1.5 rounded-full text-body touch-target ${chipH} ${on(c) ? "bg-nx-ink font-medium text-nx-on-ink" : "bg-nx-ink/5 hover:bg-nx-ink/10"}`}>
            {on(c) && <Check aria-hidden className="h-4 w-4" strokeWidth={2.25} />}{t(`discovery.correction.${key}`)}
          </button>
        ))}
      </div>
      {(on("stories") || on("area")) && (
        <div className="flex flex-col gap-3 rounded-2xl bg-nx-block p-3">
          {on("stories") && (
            <label className="flex items-center gap-2.5 text-body">
              <input ref={storiesRef} type="text" inputMode="numeric" pattern="[0-9]*" maxLength={3} aria-label={t("discovery.correction.storiesLabel")}
                value={form.stories} onFocus={(e) => e.currentTarget.select()} data-testid="correction-stories"
                onChange={(e) => { const v = e.target.value.replace(/\D/g, ""); setForm((f) => ({ ...f, stories: v })); }}
                className="h-10 w-16 rounded-xl bg-nx-page text-center text-[1.0625rem] font-semibold tabular-nums text-nx-ink ring-1 ring-nx-ink/15 focus:outline-none focus:ring-nx-ink/60" />
              <span>{t("discovery.correction.storiesUnit")}</span>
            </label>
          )}
          {on("area") && (
            <div role="group" aria-label={t("discovery.correction.areaLabel")}
              className="grid max-w-[18rem] grid-cols-2 gap-1 rounded-full bg-nx-page p-1 text-body ring-1 ring-nx-ink/15">
              {(["high", "low"] as const).map((k) => (
                <button key={k} type="button" aria-pressed={form.area === k} onClick={() => setForm((f) => ({ ...f, area: k }))} data-area={k}
                  className={`inline-flex h-8 items-center justify-center rounded-full touch-target ${form.area === k ? "bg-nx-ink font-medium text-nx-on-ink" : "hover:bg-nx-ink/5"}`}>
                  {t(k === "high" ? "discovery.correction.areaHigh" : "discovery.correction.areaLow")}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      <textarea ref={noteRef} rows={3} maxLength={NOTE_MAX} value={form.note} placeholder={t("discovery.correction.note")}
        aria-label={t("discovery.correction.note")} data-testid="correction-note"
        onChange={(e) => { const v = e.target.value; setForm((f) => ({ ...f, note: v })); }}
        className="resize-none rounded-2xl bg-nx-block px-4 py-3 text-body text-nx-ink placeholder:text-nx-ink/60 focus:outline-none focus:ring-1 focus:ring-nx-ink/60" />
    </div>
  );
}

export interface SuggestCorrectionProps {
  pin10: string;
  /** The lot's address as the card shows it (under the question). */
  title: string;
  hasBuilding: boolean;
  condo: boolean;
  /** The phone's sheet over the whole screen, else the laptop's centered dialog. */
  phone: boolean;
}

/** The pencil (a muted check once this browser sent a report for the lot) and the form it opens. */
export function SuggestCorrection({ pin10, title, hasBuilding, condo, phone }: SuggestCorrectionProps) {
  const { t } = useTranslation("next");
  const sent = useSent(pin10);
  const [open, setOpen] = useState(false);
  const size = phone ? "h-11 w-11" : "h-7 w-7 touch-icon";
  if (sent) {
    return (
      <span className="group relative" data-testid="correction-sent">
        <span tabIndex={0} role="img" aria-label={t("discovery.correction.sent")} className={`${ICON_BTN} ${size} hover:bg-transparent focus-visible:outline focus-visible:outline-2`}>
          <Check aria-hidden className={phone ? "h-5 w-5 nx-muted" : "h-4 w-4 nx-muted"} strokeWidth={STROKE} />
        </span>
        <Tip label={t("discovery.correction.sent")} />
      </span>
    );
  }
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <span className="group relative">
        <Dialog.Trigger asChild>
          <button type="button" aria-label={t("discovery.correction.suggest")} data-testid="correction-open" className={`${ICON_BTN} ${size}`}>
            <PencilLine aria-hidden className={phone ? "h-5 w-5 nx-muted" : "h-4 w-4 nx-muted"} strokeWidth={STROKE} />
          </button>
        </Dialog.Trigger>
        <Tip label={t("discovery.correction.suggest")} />
      </span>
      {open && <CorrectionDialog pin10={pin10} title={title} lot={{ hasBuilding, condo }} phone={phone} onDone={() => setOpen(false)} />}
    </Dialog.Root>
  );
}

function CorrectionDialog({ pin10, title, lot, phone, onDone }: {
  pin10: string; title: string; lot: { hasBuilding: boolean; condo: boolean }; phone: boolean; onDone: () => void;
}) {
  const { t } = useTranslation("next");
  const [form, setForm] = useState<CorrectionForm>(EMPTY_FORM);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<"too_many" | "failed" | null>(null);
  const ready = formReady(form) && !busy;

  async function send() {
    if (!formReady(form) || busy) return;
    setBusy(true);
    setError(null);
    const result = await sendLotCorrection(toBody(pin10, form));
    setBusy(false);
    if (result === "sent") {
      markSent(pin10);
      onDone();
      showToast(t("discovery.correction.thanks"));
    } else {
      setError(result); // the form keeps what was typed
    }
  }

  const head = (
    <div className="flex flex-col gap-0.5 pr-10">
      <Dialog.Title className="text-[1.0625rem] font-semibold leading-snug">{t("discovery.correction.question")}</Dialog.Title>
      <Dialog.Description className="text-caption nx-muted [overflow-wrap:anywhere]">{title}</Dialog.Description>
    </div>
  );
  const errorLine = error && (
    <p role="alert" className="rounded-xl bg-nx-pill-red-bg px-4 py-3 text-caption text-nx-pill-red" data-testid="correction-error">
      {t(error === "too_many" ? "discovery.correction.tooMany" : "discovery.correction.failed")}
    </p>
  );
  const sendLabel = busy ? t("discovery.correction.sending") : t("discovery.correction.send");
  const close = (
    <Dialog.Close asChild>
      <button type="button" aria-label={t("discovery.correction.close")} className={`${ICON_BTN} h-11 w-11`} data-testid="correction-close">
        <X aria-hidden className="h-5 w-5" strokeWidth={STROKE} />
      </button>
    </Dialog.Close>
  );

  return (
    <Dialog.Portal>
      <div className="ui-next">
        <Dialog.Overlay className="fixed inset-0 z-[65] bg-black/30" />
        {phone ? (
          <PhoneSheet onClose={onDone} close={close}>
            <form onSubmit={(e) => { e.preventDefault(); void send(); }} className="flex min-h-0 flex-1 flex-col">
              <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-5 pb-4 pt-1">
                {head}
                <FormBody form={form} setForm={setForm} lot={lot} big />
                {errorLine}
              </div>
              <div className="border-t border-nx-ink/10 px-5 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-3">
                <button type="submit" disabled={!ready} className={`${BTN_PRIMARY} h-12 w-full text-body`} data-testid="correction-send">{sendLabel}</button>
              </div>
            </form>
          </PhoneSheet>
        ) : (
          <Dialog.Content data-testid="correction-dialog"
            className="fixed left-1/2 top-1/2 z-[70] w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-3xl bg-nx-page p-6 text-nx-ink shadow-[0_8px_32px_rgb(0_0_0/0.25)]">
            <span className="absolute right-3 top-3">{close}</span>
            <form onSubmit={(e) => { e.preventDefault(); void send(); }} className="flex flex-col gap-5">
              {head}
              <FormBody form={form} setForm={setForm} lot={lot} big={false} />
              {errorLine}
              <div className="flex justify-end gap-2">
                <Dialog.Close asChild><button type="button" className={BTN_SECONDARY}>{t("discovery.correction.cancel")}</button></Dialog.Close>
                <button type="submit" disabled={!ready} className={BTN_PRIMARY} data-testid="correction-send">{sendLabel}</button>
              </div>
            </form>
          </Dialog.Content>
        )}
      </div>
    </Dialog.Portal>
  );
}

/** The phone's form: a sheet that slides up over the whole screen, a 24 px strip of the dimmed map above it; drag the
 * handle down past 120 px (or ×) to close. */
function PhoneSheet({ onClose, close, children }: { onClose: () => void; close: React.ReactNode; children: React.ReactNode }) {
  const [dy, setDy] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [shown, setShown] = useState(false);
  const start = useRef<number | null>(null);
  useEffect(() => { const id = requestAnimationFrame(() => setShown(true)); return () => cancelAnimationFrame(id); }, []);
  return (
    <Dialog.Content data-testid="correction-dialog" data-sheet=""
      style={{ transform: `translateY(${shown ? `${dy}px` : "100%"})`, transition: dragging ? "none" : undefined }}
      className="fixed inset-x-0 bottom-0 top-6 z-[70] flex flex-col rounded-t-3xl bg-nx-page text-nx-ink shadow-[0_-8px_32px_rgb(0_0_0/0.2)] transition-transform duration-[250ms] ease-out motion-reduce:transition-none">
      <div className="flex shrink-0 cursor-grab touch-none select-none justify-center pb-2 pt-3" data-testid="correction-handle"
        onPointerDown={(e) => { start.current = e.clientY; setDragging(true); try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch { /* jsdom */ } }}
        onPointerMove={(e) => { if (start.current != null) setDy(Math.max(0, e.clientY - start.current)); }}
        onPointerUp={(e) => {
          const far = start.current != null && e.clientY - start.current > 120;
          start.current = null; setDragging(false); setDy(0);
          if (far) onClose();
        }}
        onPointerCancel={() => { start.current = null; setDragging(false); setDy(0); }}>
        <span aria-hidden className="h-1 w-10 rounded-full bg-nx-ink/20" />
      </div>
      <span className="absolute right-2 top-2">{close}</span>
      {children}
    </Dialog.Content>
  );
}
