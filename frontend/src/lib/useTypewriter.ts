import { useEffect, useRef, useState } from "react";
import { TYPEWRITER_CHAR_DELAY_MS as CHAR_DELAY_MS } from "./constants";

export function useTypewriter(content: string, streaming: boolean): string {
  const [displayedLength, setDisplayedLength] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const contentRef = useRef(content);

  // Keep content ref updated for interval closure
  contentRef.current = content;

  useEffect(() => {
    // Always clear existing interval first
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (!streaming) {
      // Not streaming — show everything immediately
      setDisplayedLength(content.length);
      return;
    }

    // Streaming — advance characters over time
    intervalRef.current = setInterval(() => {
      setDisplayedLength((prev) => {
        const target = contentRef.current.length;
        if (prev >= target) return prev;
        // Advance 1-2 chars per tick for smoother feel
        return Math.min(prev + 1, target);
      });
    }, CHAR_DELAY_MS);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [streaming, content.length]);

  // Reset displayed length when content is cleared (new message)
  useEffect(() => {
    if (content.length === 0) {
      setDisplayedLength(0);
    }
  }, [content.length]);

  return content.slice(0, displayedLength);
}
