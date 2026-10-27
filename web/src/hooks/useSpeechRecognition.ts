import { useCallback, useEffect, useRef, useState } from "react";

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

interface SpeechRecognitionLike extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechResultEventLike) => void) | null;
  onerror: ((event: SpeechErrorEventLike) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
}

interface SpeechResultEventLike extends Event {
  results: ArrayLike<
    ArrayLike<{ transcript: string }> & { isFinal?: boolean }
  >;
}

interface SpeechErrorEventLike extends Event {
  error: string;
}

interface SpeechWindow extends Window {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
}

const ERROR_MESSAGES: Record<string, string> = {
  "not-allowed": "No se concedió permiso para usar el micrófono.",
  "service-not-allowed": "El reconocimiento de voz no está permitido en este navegador.",
  "no-speech": "No se detectó voz. Intenta de nuevo.",
  "audio-capture": "No se encontró un micrófono disponible.",
  network: "El servicio de reconocimiento de voz no está disponible.",
  aborted: "El reconocimiento de voz se detuvo.",
};

const MAX_LISTEN_MS = 12_000;

export function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const speechWindow = window as SpeechWindow;
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
}

export function useSpeechRecognition(onResult: (text: string) => void) {
  const [supported] = useState(() => getSpeechRecognitionConstructor() !== null);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const timerRef = useRef<number | null>(null);
  const mounted = useRef(true);
  const resultHandler = useRef(onResult);
  resultHandler.current = onResult;

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    clearTimer();
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    if (mounted.current) {
      setListening(false);
      setInterim("");
    }
  }, [clearTimer]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      clearTimer();
      recognitionRef.current?.abort();
      recognitionRef.current = null;
    };
  }, [clearTimer]);

  const start = useCallback(() => {
    if (!supported) {
      setError("El reconocimiento de voz no es compatible con este navegador.");
      return;
    }
    if (recognitionRef.current) {
      stop();
      return;
    }

    const Constructor = getSpeechRecognitionConstructor();
    if (!Constructor) return;
    const recognition = new Constructor();
    recognition.lang = "es-MX";
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      if (!mounted.current || recognitionRef.current !== recognition) return;
      setListening(true);
      setInterim("");
      setError(null);
    };
    recognition.onresult = (event) => {
      if (!mounted.current || recognitionRef.current !== recognition) return;
      let interimText = "";
      let finalText = "";
      for (let i = 0; i < event.results.length; i += 1) {
        const result = event.results[i];
        const transcript = result[0]?.transcript ?? "";
        if (result.isFinal) {
          finalText += `${transcript} `;
        } else {
          interimText += transcript;
        }
      }
      if (interimText) {
        setInterim(interimText);
      }
      if (finalText.trim()) {
        setInterim("");
        resultHandler.current(finalText.trim());
        stop();
      }
    };
    recognition.onerror = (event) => {
      if (!mounted.current || recognitionRef.current !== recognition) return;
      clearTimer();
      recognitionRef.current = null;
      setListening(false);
      setInterim("");
      if (event.error === "aborted") {
        return;
      }
      setError(ERROR_MESSAGES[event.error] ?? "No se pudo completar el reconocimiento de voz.");
      // Asegura que el micrófono no quede activo tras un error.
      try {
        recognition.abort();
      } catch {
        // El reconocimiento ya pudo haberse detenido.
      }
    };
    recognition.onend = () => {
      if (!mounted.current || recognitionRef.current !== recognition) return;
      setListening(false);
      setInterim("");
      clearTimer();
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setError("No se pudo iniciar el reconocimiento de voz.");
      setListening(false);
      return;
    }
    clearTimer();
    timerRef.current = window.setTimeout(() => stop(), MAX_LISTEN_MS);
  }, [clearTimer, supported, stop]);

  return {
    supported,
    listening,
    interim,
    error,
    start,
    stop,
    clearError: () => setError(null),
  };
}
