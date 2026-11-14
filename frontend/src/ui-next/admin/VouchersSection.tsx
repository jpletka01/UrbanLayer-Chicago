// Early-adopter access management: mint voucher codes (time-boxed comp
// premium), see who redeemed what, and grant access directly by email
// (only works after the user's first sign-in — codes work before).
import { useEffect, useState } from "react";
import {
  adminGrantPremium,
  createAdminVoucher,
  fetchAdminVouchers,
  type AdminVoucher,
} from "../../lib/api";

const inputCls =
  "px-2.5 py-1.5 rounded-md bg-nx-block border border-nx-ink/10 text-caption text-nx-ink placeholder:nx-muted focus:outline-none focus:border-nx-ink/60";
const buttonCls =
  "px-3 py-1.5 rounded-md border border-nx-ink/10 text-caption nx-muted hover:underline hover:border-nx-ink/30 transition-colors disabled:opacity-50";

function CopyableCode({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      title="Copy code"
      className="font-mono text-caption text-nx-ink hover:underline transition-colors"
    >
      {code}
      {copied && <span className="ml-1.5 text-micro text-nx-pill-green">copied</span>}
    </button>
  );
}

export function VouchersSection() {
  const [vouchers, setVouchers] = useState<AdminVoucher[] | null>(null);

  const [label, setLabel] = useState("");
  const [days, setDays] = useState(30);
  const [maxRedemptions, setMaxRedemptions] = useState(1);
  const [customCode, setCustomCode] = useState("");
  const [minting, setMinting] = useState(false);
  const [mintError, setMintError] = useState<string | null>(null);

  const [grantEmail, setGrantEmail] = useState("");
  const [grantDays, setGrantDays] = useState(30);
  const [granting, setGranting] = useState(false);
  const [grantResult, setGrantResult] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    fetchAdminVouchers().then(setVouchers);
  }, []);

  async function handleMint() {
    if (minting) return;
    setMinting(true);
    setMintError(null);
    try {
      const v = await createAdminVoucher({
        label: label.trim(),
        duration_days: days,
        max_redemptions: maxRedemptions,
        code: customCode.trim() || undefined,
      });
      setVouchers((prev) => [v, ...(prev ?? [])]);
      setLabel("");
      setCustomCode("");
    } catch (err) {
      setMintError(err instanceof Error ? err.message : String(err));
    } finally {
      setMinting(false);
    }
  }

  async function handleGrant() {
    const email = grantEmail.trim();
    if (!email || granting) return;
    setGranting(true);
    setGrantResult(null);
    try {
      const res = await adminGrantPremium(email, grantDays);
      setGrantResult({
        ok: true,
        text: `${res.email} has premium until ${new Date(res.premium_until).toLocaleDateString()}`,
      });
      setGrantEmail("");
    } catch (err) {
      setGrantResult({
        ok: false,
        text: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setGranting(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* Mint a code */}
      <div>
        <div className="text-micro nx-muted uppercase tracking-wide mb-2">
          Mint a code
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Label (who / channel)"
            className={`${inputCls} w-44`}
          />
          <label className="flex items-center gap-1.5 text-caption nx-muted">
            <input
              type="number"
              min={1}
              value={days}
              onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 1))}
              className={`${inputCls} w-16`}
            />
            days
          </label>
          <label className="flex items-center gap-1.5 text-caption nx-muted">
            <input
              type="number"
              min={1}
              value={maxRedemptions}
              onChange={(e) =>
                setMaxRedemptions(Math.max(1, Number(e.target.value) || 1))
              }
              className={`${inputCls} w-16`}
            />
            uses
          </label>
          <input
            value={customCode}
            onChange={(e) => setCustomCode(e.target.value)}
            placeholder="Custom code (optional)"
            className={`${inputCls} w-44 font-mono uppercase placeholder:normal-case placeholder:font-sans`}
          />
          <button onClick={handleMint} disabled={minting} className={buttonCls}>
            {minting ? "Minting…" : "Mint code"}
          </button>
        </div>
        {mintError && (
          <p className="mt-1.5 text-caption text-nx-pill-red">{mintError}</p>
        )}
      </div>

      {/* Grant by email */}
      <div>
        <div className="text-micro nx-muted uppercase tracking-wide mb-2">
          Grant by email
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={grantEmail}
            onChange={(e) => setGrantEmail(e.target.value)}
            placeholder="user@example.com"
            className={`${inputCls} w-56`}
          />
          <label className="flex items-center gap-1.5 text-caption nx-muted">
            <input
              type="number"
              min={1}
              value={grantDays}
              onChange={(e) => setGrantDays(Math.max(1, Number(e.target.value) || 1))}
              className={`${inputCls} w-16`}
            />
            days
          </label>
          <button
            onClick={handleGrant}
            disabled={granting || !grantEmail.trim()}
            className={buttonCls}
          >
            {granting ? "Granting…" : "Grant"}
          </button>
        </div>
        {grantResult && (
          <p
            className={`mt-1.5 text-caption ${grantResult.ok ? "text-nx-pill-green" : "text-nx-pill-red"}`}
          >
            {grantResult.text}
          </p>
        )}
      </div>

      {/* Codes table */}
      {vouchers === null ? (
        <div className="nx-muted text-body text-center py-6">Loading…</div>
      ) : vouchers.length === 0 ? (
        <div className="nx-muted text-body text-center py-6">
          No codes minted yet
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-micro nx-muted uppercase tracking-wide">
                <th className="py-1.5 pr-4 font-medium">Code</th>
                <th className="py-1.5 pr-4 font-medium">Label</th>
                <th className="py-1.5 pr-4 font-medium">Days</th>
                <th className="py-1.5 pr-4 font-medium">Used</th>
                <th className="py-1.5 pr-4 font-medium">Redeemed by</th>
                <th className="py-1.5 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {vouchers.map((v) => (
                <tr key={v.code} className="border-t border-nx-ink/10 align-top">
                  <td className="py-2 pr-4 whitespace-nowrap">
                    <CopyableCode code={v.code} />
                  </td>
                  <td className="py-2 pr-4 text-caption nx-muted">
                    {v.label || "—"}
                  </td>
                  <td className="py-2 pr-4 text-caption nx-muted">
                    {v.duration_days}
                  </td>
                  <td className="py-2 pr-4 text-caption nx-muted whitespace-nowrap">
                    {v.redemptions.length}/{v.max_redemptions}
                  </td>
                  <td className="py-2 pr-4 text-caption nx-muted">
                    {v.redemptions.length === 0
                      ? "—"
                      : v.redemptions.map((r) => (
                          <div key={`${v.code}-${r.user_id}`} className="whitespace-nowrap">
                            {r.email ?? r.user_id}
                            <span className="nx-muted">
                              {" · "}
                              {new Date(r.redeemed_at).toLocaleDateString()}
                            </span>
                          </div>
                        ))}
                  </td>
                  <td className="py-2 text-caption nx-muted whitespace-nowrap">
                    {new Date(v.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
