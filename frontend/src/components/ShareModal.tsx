import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { createShareLink, getShareStatus, revokeShareLink } from "../lib/api";
import { Modal } from "./ui/Modal";

interface ShareModalProps {
  conversationId: string;
  onClose: () => void;
}

export function ShareModal({ conversationId, onClose }: ShareModalProps) {
  const { t } = useTranslation("common");
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
    <Modal onClose={onClose} size="md" showClose={false} title={t("shareTitle")} description={t("shareDescription")}>
      {loading ? (
        <div className="flex items-center justify-center py-6">
          <div className="w-5 h-5 border-2 border-text-muted border-t-accent rounded-full animate-spin" />
          <span className="ml-3 text-body text-text-muted">{t("creatingLink")}</span>
        </div>
      ) : url ? (
        <>
          <div className="flex items-center gap-2 mb-4">
            <input
              type="text"
              readOnly
              value={url}
              className="flex-1 bg-dark-bg border border-dark-border rounded-lg px-3 py-2 text-body text-text-primary font-mono truncate"
              onClick={(e) => (e.target as HTMLInputElement).select()}
            />
            <button
              onClick={handleCopy}
              className="shrink-0 px-4 py-2 text-title rounded-lg transition-colors bg-accent text-text-on-accent hover:bg-accent-hover"
            >
              {copied ? t("copied") : t("copy")}
            </button>
          </div>
          <div className="flex items-center justify-between">
            <button
              onClick={handleRevoke}
              disabled={revoking}
              className="text-caption text-text-muted hover:text-rose-400 transition-colors disabled:opacity-50"
            >
              {revoking ? t("revoking") : t("revokeLink")}
            </button>
            <button
              onClick={onClose}
              className="px-4 py-1.5 text-body text-text-secondary hover:text-text-primary transition-colors"
            >
              {t("done")}
            </button>
          </div>
        </>
      ) : (
        <div className="text-center py-4">
          <p className="text-body text-text-muted mb-4">{t("linkRevoked")}</p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={async () => {
                setLoading(true);
                const result = await createShareLink(conversationId);
                if (result) setUrl(result.url);
                setLoading(false);
              }}
              className="px-4 py-1.5 text-title rounded-lg bg-accent text-text-on-accent hover:bg-accent-hover transition-colors"
            >
              {t("createNewLink")}
            </button>
            <button
              onClick={onClose}
              className="px-4 py-1.5 text-body text-text-secondary hover:text-text-primary transition-colors"
            >
              {t("close")}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
