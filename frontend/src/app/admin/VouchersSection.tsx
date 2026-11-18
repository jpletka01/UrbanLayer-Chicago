// "Early access" (owner's review 2026-11-17: "we could do better than this UI for creating codes"): make a code in
// one card (who it's for, how long, how many uses; the code itself is made up unless you type one), give an account
// Pro by email beside it, and the codes as rows: the code with a copy button, how long it lasts and how many used it
// as pills, who used it one click away. Same endpoints as before. English only, like the rest of /admin.
import { useEffect, useState } from "react";
import { Check, ChevronDown, Clock, Copy, Mail, Minus, Plus, Sparkles, Ticket, Users } from "lucide-react";
import { adminGrantPremium, createAdminVoucher, fetchAdminVouchers, type AdminVoucher } from "../../lib/api";
import { STROKE } from "../icons";
import { Block, Pill } from "../ui/Blocks";
import { Empty, IconAction } from "./adminUi";

const LENGTHS = [7, 30, 90, 365] as const;
const FIELD = "h-10 w-full rounded-xl bg-nx-page px-3 text-body ring-1 ring-nx-ink/15 placeholder:text-nx-ink/50 focus:outline-none focus:ring-nx-ink/60";
const PRIMARY = "inline-flex h-10 items-center justify-center gap-2 rounded-full bg-nx-primary px-5 font-semibold text-nx-primary-fg disabled:opacity-40 touch-target";
const lengthWord = (d: number) => (d === 365 ? "1 year" : `${d} days`);
const day = (ms: number) => new Date(ms).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

/** Length chips: the usual choices, picked = ink. */
function LengthChips({ value, onChange, label }: { value: number; onChange: (d: number) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1.5">
      {LENGTHS.map((d) => (
        <button key={d} type="button" role="radio" aria-checked={value === d} onClick={() => onChange(d)}
          className={`h-8 rounded-full px-3 text-caption touch-target ${value === d ? "bg-nx-ink font-medium text-nx-on-ink" : "bg-nx-ink/5 hover:bg-nx-ink/10"}`}>
          {lengthWord(d)}
        </button>
      ))}
    </div>
  );
}

export function VouchersSection() {
  const [vouchers, setVouchers] = useState<AdminVoucher[] | null>(null);
  useEffect(() => { fetchAdminVouchers().then(setVouchers); }, []);

  return (
    <div className="flex flex-col gap-4" data-testid="early-access">
      <div className="nx-cq"><div className="nx-split nx-split-even">
        <NewCode onMade={(v) => setVouchers((prev) => [v, ...(prev ?? [])])} />
        <GrantByEmail />
      </div></div>
      <Block title="Codes" icon={Ticket} aside={vouchers?.length ? `${vouchers.length}` : undefined}>
        {vouchers === null ? <p className="text-caption nx-muted">Loading…</p>
          : vouchers.length === 0 ? <Empty icon={Ticket}>No codes yet.</Empty>
            : <ul className="flex flex-col divide-y divide-nx-ink/10" data-testid="voucher-list">{vouchers.map((v) => <CodeRow key={v.code} v={v} />)}</ul>}
      </Block>
    </div>
  );
}

function NewCode({ onMade }: { onMade: (v: AdminVoucher) => void }) {
  const [label, setLabel] = useState("");
  const [days, setDays] = useState(30);
  const [uses, setUses] = useState(1);
  const [custom, setCustom] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [made, setMade] = useState<string | null>(null);

  async function make() {
    if (busy) return;
    setBusy(true); setError(null); setMade(null);
    try {
      const v = await createAdminVoucher({ label: label.trim(), duration_days: days, max_redemptions: uses, code: custom.trim() || undefined });
      onMade(v); setMade(v.code); setLabel(""); setCustom("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally { setBusy(false); }
  }

  return (
    <Block title="New code" icon={Sparkles}>
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); void make(); }} data-testid="voucher-new">
        <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Who it's for" aria-label="Who it's for" className={FIELD} />
        <div className="flex flex-col gap-1.5">
          <span className="flex items-center gap-1.5 text-caption nx-muted"><Clock aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />Pro for</span>
          <LengthChips value={days} onChange={setDays} label="Pro for" />
        </div>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex flex-col gap-1.5">
            <span className="flex items-center gap-1.5 text-caption nx-muted"><Users aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />Uses</span>
            <div className="inline-flex items-center gap-1 rounded-full bg-nx-page p-1 ring-1 ring-nx-ink/15">
              <IconAction label="One fewer use" icon={Minus} onClick={() => setUses((u) => Math.max(1, u - 1))} disabled={uses <= 1} />
              <span className="w-8 text-center font-semibold tabular-nums" aria-live="polite" data-testid="voucher-uses">{uses}</span>
              <IconAction label="One more use" icon={Plus} onClick={() => setUses((u) => Math.min(999, u + 1))} />
            </div>
          </div>
          <input value={custom} onChange={(e) => setCustom(e.target.value.toUpperCase())} placeholder="Own code (optional)" aria-label="Own code (optional)"
            className={`${FIELD} max-w-[13rem] font-mono placeholder:font-sans`} />
        </div>
        {error && <p role="alert" className="text-caption text-nx-pill-red">{error}</p>}
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" disabled={busy} className={PRIMARY} data-testid="voucher-make"><Ticket aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{busy ? "Making…" : "Make code"}</button>
          {made && <span role="status" className="flex items-center gap-1.5 text-caption"><Check aria-hidden className="h-4 w-4 text-nx-pill-green" strokeWidth={STROKE} /><span className="font-mono">{made}</span> ready</span>}
        </div>
      </form>
    </Block>
  );
}

function GrantByEmail() {
  const [email, setEmail] = useState("");
  const [days, setDays] = useState(30);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);

  async function grant() {
    const e = email.trim();
    if (!e || busy) return;
    setBusy(true); setResult(null);
    try {
      const res = await adminGrantPremium(e, days);
      setResult({ ok: true, text: `Pro until ${day(res.premium_until)}` });
      setEmail("");
    } catch (err) {
      setResult({ ok: false, text: err instanceof Error ? err.message : String(err) });
    } finally { setBusy(false); }
  }

  return (
    <Block title="Give Pro by email" icon={Mail} aside="After their first sign-in">
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); void grant(); }} data-testid="voucher-grant">
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" aria-label="Email" className={FIELD} />
        <div className="flex flex-col gap-1.5">
          <span className="flex items-center gap-1.5 text-caption nx-muted"><Clock aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />Pro for</span>
          <LengthChips value={days} onChange={setDays} label="Pro for, by email" />
        </div>
        {result && <p role={result.ok ? "status" : "alert"} className={`text-caption ${result.ok ? "text-nx-pill-green" : "text-nx-pill-red"}`}>{result.text}</p>}
        <div><button type="submit" disabled={busy || !email.trim()} className={PRIMARY}><Mail aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{busy ? "Giving…" : "Give Pro"}</button></div>
      </form>
    </Block>
  );
}

function CodeRow({ v }: { v: AdminVoucher }) {
  const [copied, setCopied] = useState(false);
  const [open, setOpen] = useState(false);
  const used = v.redemptions.length;
  const full = used >= v.max_redemptions;
  return (
    <li className="py-2.5" data-testid="voucher-row">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="font-mono font-semibold">{v.code}</span>
        <IconAction label={copied ? "Copied" : `Copy ${v.code}`} icon={copied ? Check : Copy}
          onClick={() => { void navigator.clipboard?.writeText(v.code); setCopied(true); window.setTimeout(() => setCopied(false), 1500); }} />
        <span className="min-w-0 flex-1 truncate text-caption nx-muted">{v.label || "No label"}</span>
        <span className="flex flex-wrap items-center gap-1.5">
          <Pill icon={Clock}>{lengthWord(v.duration_days)}</Pill>
          <Pill tone={full ? "green" : used ? "blue" : "gray"} icon={Users}>{used} of {v.max_redemptions} used</Pill>
          {v.disabled ? <Pill tone="red">Off</Pill> : null}
          {used > 0 && <IconAction label={open ? "Hide who used it" : "Who used it"} icon={ChevronDown} onClick={() => setOpen((o) => !o)} pressed={open} />}
        </span>
      </div>
      {open && (
        <ul className="mt-2 flex flex-col gap-1 rounded-xl bg-nx-ink/[0.03] px-3 py-2 text-caption">
          {v.redemptions.map((r) => (
            <li key={r.user_id} className="flex justify-between gap-3"><span className="truncate">{r.email ?? r.name ?? r.user_id}</span><span className="nx-muted">{day(r.redeemed_at)}</span></li>
          ))}
        </ul>
      )}
    </li>
  );
}
