import type { Servidor } from "../types/api";

export type VoiceCommand =
  | { type: "save"; servidor: Servidor | null; text: string }
  | { type: "unknown"; text: string };

export function normalizeVoiceText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[.,;:!?¡¿]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const UBUNTU_MARKERS = [
  "ubuntu",
  "postgres",
  "postgresql",
  "servidor 1",
  "servidor uno",
  "primer servidor",
  "1",
];
const WINDOWS_MARKERS = [
  "windows",
  "sql server",
  "servidor 2",
  "servidor dos",
  "segundo servidor",
  "2",
];

function containsPhrase(text: string, phrase: string): boolean {
  return new RegExp(`(^|\\s)${phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(\\s|$)`).test(
    text,
  );
}

export function parseVoiceCommand(rawText: string): VoiceCommand {
  const text = normalizeVoiceText(rawText);
  if (!text) {
    return { type: "unknown", text: rawText };
  }

  const isSave = containsPhrase(text, "guardar") || containsPhrase(text, "guarda");
  if (!isSave) {
    return { type: "unknown", text: rawText };
  }

  const ubuntu = UBUNTU_MARKERS.some((marker) => containsPhrase(text, marker));
  const windows = WINDOWS_MARKERS.some((marker) => containsPhrase(text, marker));

  if (ubuntu && !windows) {
    return { type: "save", servidor: "ubuntu", text: rawText };
  }
  if (windows && !ubuntu) {
    return { type: "save", servidor: "windows", text: rawText };
  }
  if (ubuntu && windows) {
    // "guardar en servidor 1 o 2" no identifica un destino único.
    return { type: "unknown", text: rawText };
  }
  return { type: "save", servidor: null, text: rawText };
}
