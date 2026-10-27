const rawBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() ?? "";

/**
 * Origen del backend, sin barra final. Puede quedar vacío para servir la API
 * desde el mismo origen que el frontend (proxy inverso).
 */
export const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");

export const API_PREFIX = "/api";
export const REQUEST_TIMEOUT_MS = 15_000;
export const AUTH_EXPIRED_EVENT = "clima:auth-expired";
