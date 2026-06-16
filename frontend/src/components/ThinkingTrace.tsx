import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

interface Props {
  collapsed: boolean;
}

export function ThinkingTrace({ collapsed }: Props) {
  const { t } = useTranslation("chat");
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    if (collapsed) {
      const t = setTimeout(() => setHidden(true), 350);
      return () => clearTimeout(t);
    }
    setHidden(false);
  }, [collapsed]);

  if (hidden) return null;

  return (
    <div
      className={`flex items-center gap-2.5 transition-opacity duration-300 ${
        collapsed ? "opacity-0" : "opacity-100"
      }`}
    >
      <div className="flex gap-1 items-end">
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-dot-bounce" style={{ animationDelay: "0ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-dot-bounce" style={{ animationDelay: "200ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-dot-bounce" style={{ animationDelay: "400ms" }} />
      </div>
      <span className="text-sm font-medium animate-text-glow">{t("thinking")}</span>
    </div>
  );
}
