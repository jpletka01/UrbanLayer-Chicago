import ReactMarkdown from "react-markdown";
import type { Message } from "../lib/types";
import { DisclaimerBanner } from "./DisclaimerBanner";

interface Props {
  message: Message;
  streaming?: boolean;
  showDisclaimer?: boolean;
}

export function MessageBubble({ message, streaming, showDisclaimer }: Props) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-5 py-3 ${
          isUser
            ? "bg-sky-600 text-white"
            : "bg-white border border-slate-200 text-slate-800 shadow-sm"
        }`}
      >
        {isUser ? (
          <p className="text-base leading-relaxed whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-slate prose-sm max-w-none text-base leading-relaxed">
            <ReactMarkdown
              components={{
                p: ({ children }) => <p className="text-slate-800 text-base leading-relaxed mb-4 last:mb-0">{children}</p>,
                a: ({ children, ...props }) => (
                  <a
                    {...props}
                    className="cursor-pointer text-sky-600 hover:text-sky-700 underline decoration-dotted font-medium"
                  >
                    {children}
                  </a>
                ),
                ul: ({ children }) => <ul className="list-disc pl-5 mb-4 space-y-1">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal pl-5 mb-4 space-y-1">{children}</ol>,
                strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
              }}
            >
              {message.content}
            </ReactMarkdown>
            {streaming && (
              <span className="inline-block w-2 h-4 bg-sky-600 animate-pulse align-text-bottom ml-0.5" />
            )}
            {showDisclaimer && <DisclaimerBanner />}
          </div>
        )}
      </div>
    </div>
  );
}
