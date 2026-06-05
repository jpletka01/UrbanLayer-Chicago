import { useCallback, useEffect, useState } from "react";
import { createShareLink, getShareStatus, revokeShareLink } from "../lib/api";

interface ShareModalProps {
  conversationId: string;
  onClose: () => void;
}

export function ShareModal({ conversationId, onClose }: ShareModalProps) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [revoking, setRevoking] = useState(false);

  useEffect(() => {
    (async () => {
      const status = await getShareStatus(conversationId);
      if (status.shared && status.url) {
        setUrl(status.url);
        setLoading(false);
      } else {
        const result = await createShareLink(conversationId);
        if (result) {
          setUrl(result.url);
        }
        setLoading(false);
      }
    })();
  }, [conversationId]);

  const handleCopy = useCallback(async () => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const input = document.createElement("input");
      input.value = url;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [url]);

  const handleRevoke = useCallback(async () => {
    setRevoking(true);
    await revokeShareLink(conversationId);
    setUrl(null);
    setRevoking(false);
  }, [conversationId]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md mx-4 bg-dark-surface border border-dark-border rounded-2xl p-6 shadow-2xl">
        <h2 className="text-lg font-semibold text-text-primary mb-1">
          Share this conversation
        </h2>
        <p className="text-sm text-text-secondary mb-5">
          Anyone with this link can view this conversation read-only.
        </p>

        {loading ? (
          <div className="flex items-center justify-center py-6">
            <div className="w-5 h-5 border-2 border-text-muted border-t-accent rounded-full animate-spin" />
            <span className="ml-3 text-sm text-text-muted">Creating link...</span>
          </div>
        ) : url ? (
          <>
            <div className="flex items-center gap-2 mb-4">
              <input
                type="text"
                readOnly
                value={url}
                className="flex-1 bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-sm text-text-primary font-mono truncate"
                onClick={(e) => (e.target as HTMLInputElement).select()}
              />
              <button
                onClick={handleCopy}
                className="shrink-0 px-4 py-2 text-sm font-medium rounded-lg transition-colors bg-accent text-white hover:bg-accent/90"
              >
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <div className="flex items-center justify-between">
              <button
                onClick={handleRevoke}
                disabled={revoking}
                className="text-xs text-text-muted hover:text-rose-400 transition-colors disabled:opacity-50"
              >
                {revoking ? "Revoking..." : "Revoke link"}
              </button>
              <button
                onClick={onClose}
                className="px-4 py-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
              >
                Done
              </button>
            </div>
          </>
        ) : (
          <div className="text-center py-4">
            <p className="text-sm text-text-muted mb-4">Link has been revoked.</p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={async () => {
                  setLoading(true);
                  const result = await createShareLink(conversationId);
                  if (result) setUrl(result.url);
                  setLoading(false);
                }}
                className="px-4 py-1.5 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent/90 transition-colors"
              >
                Create new link
              </button>
              <button
                onClick={onClose}
                className="px-4 py-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
