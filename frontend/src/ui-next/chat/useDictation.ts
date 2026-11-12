// Dictation in the message box (brief "Chat"): the browser's own speech-to-text where it has one (Chrome, Edge,
// Safari); where it doesn't, the microphone isn't shown. The words land in the box; the visitor still sends.
import { useEffect, useRef, useState } from "react";

interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error: string }) => void) | null;
}

type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function dictationSupported(): boolean {
  return recognitionCtor() !== null;
}

/** `onText` receives the whole dictated text so far (final and interim), to put after what was typed. */
export function useDictation(language: string, onText: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const [failed, setFailed] = useState(false);
  const rec = useRef<Recognition | null>(null);
  const cb = useRef(onText);
  useEffect(() => { cb.current = onText; });
  useEffect(() => () => rec.current?.abort(), []);

  const start = () => {
    const Ctor = recognitionCtor();
    if (!Ctor || listening) return;
    const r = new Ctor();
    r.lang = language.startsWith("es") ? "es-MX" : "en-US";
    r.interimResults = true;
    r.continuous = false;
    r.onresult = (e) => {
      let text = "";
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0]?.transcript ?? "";
      cb.current(text.trim());
    };
    r.onend = () => setListening(false);
    r.onerror = (e) => { if (e.error !== "aborted" && e.error !== "no-speech") setFailed(true); setListening(false); };
    rec.current = r;
    setFailed(false);
    setListening(true);
    try { r.start(); } catch { setListening(false); setFailed(true); }
  };

  const stop = () => rec.current?.stop();

  return { supported: dictationSupported(), listening, failed, start, stop };
}
