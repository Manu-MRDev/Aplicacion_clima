import { API_BASE_URL, API_PREFIX, AUTH_EXPIRED_EVENT, REQUEST_TIMEOUT_MS } from "../config";
import type { ApiErrorBody } from "../types/api";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId?: string;
  readonly details?: ApiErrorBody["error"]["details"];
  readonly retryAfter?: number;
  readonly isNetworkError: boolean;

  constructor(options: {
    status: number;
    message: string;
    code?: string;
    requestId?: string;
    details?: ApiErrorBody["error"]["details"];
    retryAfter?: number;
    isNetworkError?: boolean;
  }) {
    super(options.message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code ?? "unknown";
    this.requestId = options.requestId;
    this.details = options.details;
    this.retryAfter = options.retryAfter;
    this.isNetworkError = options.isNetworkError ?? false;
  }
}

export function isAbortError(error: unknown): boolean {
  if (typeof error !== "object" || error === null || !("name" in error)) {
    return false;
  }
  return error.name === "AbortError" || error.name === "TimeoutError";
}

const FALLBACK_MESSAGES: Record<number, string> = {
  400: "La solicitud no es válida.",
  401: "La sesión no es válida o expiró.",
  403: "No tiene permisos para realizar esta operación.",
  404: "No se encontró la información solicitada.",
  409: "La operación entra en conflicto con el estado actual.",
  413: "La solicitud es demasiado grande.",
  422: "Los datos enviados no son válidos.",
  429: "Demasiadas solicitudes. Espere un momento antes de reintentar.",
  500: "El servidor encontró un error inesperado.",
  502: "El servicio externo no respondió correctamente.",
  503: "El servicio no está disponible temporalmente.",
};

function errorMessage(status: number, body: ApiErrorBody | null): string {
  const backendMessage = body?.error?.message?.trim();
  if (backendMessage) {
    return backendMessage;
  }
  return FALLBACK_MESSAGES[status] ?? "No fue posible completar la operación.";
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${API_BASE_URL}${API_PREFIX}${normalizedPath}`;
  if (!query) {
    return url;
  }
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    params.set(key, String(value));
  }
  const search = params.toString();
  return search ? `${url}?${search}` : url;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  csrfToken?: string;
  signal?: AbortSignal;
  /** Evita redirigir al login en flujos de autenticación que esperan 401. */
  suppressAuthEvent?: boolean;
  timeoutMs?: number;
  query?: Record<string, string | number | boolean | undefined | null>;
}

function notifyAuthExpired(): void {
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
}

async function parseError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody | null = null;
  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    body = null;
  }
  const retryAfterHeader = response.headers.get("Retry-After");
  const retryAfter = retryAfterHeader ? Number(retryAfterHeader) : undefined;
  return new ApiError({
    status: response.status,
    code: body?.error?.code,
    message: errorMessage(response.status, body),
    requestId: body?.error?.request_id,
    details: body?.error?.details,
    retryAfter: Number.isFinite(retryAfter) ? retryAfter : undefined,
  });
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort(new DOMException("Tiempo de espera agotado", "TimeoutError")),
    options.timeoutMs ?? REQUEST_TIMEOUT_MS,
  );

  const abortFromCaller = () => controller.abort();
  if (options.signal) {
    if (options.signal.aborted) {
      controller.abort();
    } else {
      options.signal.addEventListener("abort", abortFromCaller, { once: true });
    }
  }

  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (options.csrfToken) {
    headers["X-CSRF-Token"] = options.csrfToken;
  }

  try {
    const response = await fetch(buildUrl(path, options.query), {
      method: options.method ?? "GET",
      headers,
      credentials: "include",
      cache: "no-store",
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await parseError(response);
      if (error.status === 401 && !options.suppressAuthEvent) {
        notifyAuthExpired();
      }
      throw error;
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const text = await response.text();
    if (!text) {
      return undefined as T;
    }
    try {
      return JSON.parse(text) as T;
    } catch {
      throw new ApiError({
        status: response.status,
        code: "invalid_response",
        message: "El servidor devolvió una respuesta no válida.",
      });
    }
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (isAbortError(error)) {
      if (options.signal?.aborted) {
        throw error;
      }
      throw new ApiError({
        status: 0,
        code: "timeout",
        message: "La solicitud tardó demasiado. Verifique su conexión e intente de nuevo.",
        isNetworkError: true,
      });
    }
    throw new ApiError({
      status: 0,
      code: "network_error",
      message: "No se pudo conectar con el servidor. Verifique que la API esté disponible.",
      isNetworkError: true,
    });
  } finally {
    window.clearTimeout(timeout);
    options.signal?.removeEventListener("abort", abortFromCaller);
  }
}
