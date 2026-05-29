import { useEffect, useRef, useState } from "react";
import { TYPEWRITER_CHAR_DELAY_MS as CHAR_DELAY_MS } from "./constants";

export function useTypewriter(content: string, streaming: boolean): string {
  const [displayedLength, setDisplayedLength] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const contentRef = useRef(content);
  const streamingRef = useRef(streaming);
  const wasStreamingRef = useRef(false);

  contentRef.current = content;
  streamingRef.current = streaming;
  if (streaming) wasStreamingRef.current = true;

  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (!streaming && !wasStreamingRef.current) {
      setDisplayedLength(content.length);
      return;
    }

    intervalRef.current = setInterval(() => {
      setDisplayedLength((prev) => {
        const target = contentRef.current.length;
        if (prev >= target) {
          if (!streamingRef.current) {
            clearInterval(intervalRef.current!);
            intervalRef.current = null;
          }
          return prev;
        }
        const behind = target - prev;
        const step = behind > 50 ? 3 : behind > 20 ? 2 : 1;
        return Math.min(prev + step, target);
      });
    }, CHAR_DELAY_MS);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [streaming]);

  useEffect(() => {
    if (content.length === 0) {
      setDisplayedLength(0);
      wasStreamingRef.current = false;
    }
  }, [content.length]);

  return content.slice(0, displayedLength);
}
