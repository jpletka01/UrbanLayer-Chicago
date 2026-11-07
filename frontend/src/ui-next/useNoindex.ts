// `<meta name="robots" content="noindex">` while a preview-only page is on screen (decision Item 76).
import { useEffect } from "react";

export function useNoindex(active: boolean) {
  useEffect(() => {
    if (!active || typeof document === "undefined") return;
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex";
    meta.setAttribute("data-ui-preview", "");
    document.head.appendChild(meta);
    return () => meta.remove();
  }, [active]);
}
