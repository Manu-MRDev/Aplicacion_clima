import type { CurrentWeather } from "../types/weather";

const LOCALE = "es-MX";

function safeDate(value: string | number | Date): Date | null {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateTime(value: string | null | undefined, timeZone?: string): string {
  if (!value) return "—";
  const date = safeDate(value);
  if (!date) return "—";
  try {
    return new Intl.DateTimeFormat(LOCALE, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: timeZone || undefined,
    }).format(date);
  } catch {
    return new Intl.DateTimeFormat(LOCALE, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  }
}

export function formatTime(value: string | null | undefined, timeZone?: string): string {
  if (!value) return "—";
  const date = safeDate(value);
  if (!date) return "—";
  try {
    return new Intl.DateTimeFormat(LOCALE, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      timeZone: timeZone || undefined,
    }).format(date);
  } catch {
    return new Intl.DateTimeFormat(LOCALE, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date);
  }
}

export function formatNumber(
  value: number | null | undefined,
  maximumFractionDigits = 1,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(LOCALE, {
    maximumFractionDigits,
  }).format(value);
}

export function toDateTimeLocalValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

/**
 * Convierte un valor de <input type="datetime-local"> (hora local del navegador)
 * a ISO UTC. Devuelve null si el valor está vacío.
 */
export function localDateTimeToUtc(value: string): string | null {
  if (!value.trim()) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

/**
 * Open-Meteo devuelve la hora de observación como hora local sin offset. Se usa
 * utc_offset_seconds para obtener el instante UTC real.
 */
export function observedAtToUtc(weather: CurrentWeather): string | null {
  const raw = weather.observed_at?.trim();
  if (!raw) return null;

  if (/([zZ]|[+-]\d{2}:?\d{2})$/.test(raw)) {
    const parsed = new Date(raw);
    return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
  }

  const match = raw.match(
    /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/,
  );
  if (!match) return null;
  const [, year, month, day, hour, minute, second = "0"] = match;
  const wallClock = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second),
  );
  if (Number.isNaN(wallClock)) return null;
  // Sin offset no se puede afirmar el instante real: mejor no precargar una
  // fecha que inventar una zona horaria.
  if (weather.utc_offset_seconds === null || weather.utc_offset_seconds === undefined) {
    return null;
  }
  const offset = Number(weather.utc_offset_seconds);
  if (!Number.isFinite(offset)) {
    return null;
  }
  return new Date(wallClock - offset * 1000).toISOString();
}

export function formatExpiration(seconds: number | null): string {
  if (seconds === null || seconds <= 0) return "0 s";
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes} min ${rest} s` : `${minutes} min`;
}
