import { useState } from "react";
import { copyToClipboard } from "./clipboard";

const COPY_RESET_MS = 2000;

/**
 * Copy-to-clipboard with a transient "copied" flag for button feedback.
 * Shared by the message bubble, source citation, and section drawer.
 */
export function useCopyButton(text: string) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    if (!text) return;
    const success = await copyToClipboard(text);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), COPY_RESET_MS);
    }
  };

  return { copied, copy };
}
