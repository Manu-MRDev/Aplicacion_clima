import { describe, expect, it, vi } from "vitest";

import { AUTH_EXPIRED_EVENT } from "../config";
import { ApiError, apiRequest } from "../services/apiClient";
import { errorResponse, installFetchMock, jsonResponse } from "./http";

describe("apiRequest", () => {
  it("envía cookies y no añade CSRF en lecturas", async () => {
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/records",
        respond: () => jsonResponse({ ok: true }),
      },
    ]);
    await apiRequest("/records");
    expect(mock.calls[0].headers.get("Accept")).toBe("application/json");
    expect(mock.calls[0].headers.get("X-CSRF-Token")).toBeNull();
    mock.restore();
  });

  it("añade X-CSRF-Token y JSON en escrituras", async () => {
    const mock = installFetchMock([
      {
        method: "POST",
        path: "/api/records",
        respond: () => jsonResponse({ ok: true }, 201),
      },
    ]);
    await apiRequest("/records", {
      method: "POST",
      body: { nombre: "Ana" },
      csrfToken: "csrf-123",
    });
    expect(mock.calls[0].headers.get("X-CSRF-Token")).toBe("csrf-123");
    expect(mock.calls[0].headers.get("Content-Type")).toBe("application/json");
    expect(mock.calls[0].body).toEqual({ nombre: "Ana" });
    mock.restore();
  });

  it("convierte errores del backend en ApiError con mensaje seguro", async () => {
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/records",
        respond: () =>
          errorResponse(503, "database_unavailable", "El servicio de datos no está disponible."),
      },
    ]);
    await expect(apiRequest("/records")).rejects.toMatchObject({
      name: "ApiError",
      status: 503,
      code: "database_unavailable",
      message: "El servicio de datos no está disponible.",
    });
    mock.restore();
  });

  it("emite sesión expirada en 401 de rutas privadas", async () => {
    const listener = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, listener);
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/records",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida o expirada"),
      },
    ]);
    await expect(apiRequest("/records")).rejects.toBeInstanceOf(ApiError);
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener(AUTH_EXPIRED_EVENT, listener);
    mock.restore();
  });

  it("no emite sesión expirada en flujos de autenticación", async () => {
    const listener = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, listener);
    const mock = installFetchMock([
      {
        method: "POST",
        path: "/api/auth/login",
        respond: () => errorResponse(401, "unauthorized", "Credenciales inválidas"),
      },
    ]);
    await expect(
      apiRequest("/auth/login", {
        method: "POST",
        body: { username: "ana", password: "mal" },
        suppressAuthEvent: true,
      }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(listener).not.toHaveBeenCalled();
    window.removeEventListener(AUTH_EXPIRED_EVENT, listener);
    mock.restore();
  });

  it("maneja errores de red sin exponer detalles internos", async () => {
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/records",
        respond: () => {
          throw new TypeError("fetch failed: socket hang up");
        },
      },
    ]);
    await expect(apiRequest("/records")).rejects.toMatchObject({
      code: "network_error",
      status: 0,
      message: expect.stringContaining("No se pudo conectar"),
    });
    mock.restore();
  });

  it("clasifica el tiempo de espera como timeout, no como error de red", async () => {
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/records",
        respond: ({ signal }) =>
          new Promise<Response>((_resolve, reject) => {
            signal?.addEventListener("abort", () => reject(signal.reason), {
              once: true,
            });
          }),
      },
    ]);
    await expect(apiRequest("/records", { timeoutMs: 20 })).rejects.toMatchObject({
      name: "ApiError",
      code: "timeout",
      status: 0,
    });
    mock.restore();
  });

  it("propaga la cancelación del llamador sin convertirla en error de API", async () => {
    const controller = new AbortController();
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/records",
        respond: ({ signal }) =>
          new Promise<Response>((_resolve, reject) => {
            signal?.addEventListener("abort", () => reject(signal.reason), {
              once: true,
            });
          }),
      },
    ]);
    const request = apiRequest("/records", {
      signal: controller.signal,
      timeoutMs: 1_000,
    });
    controller.abort();
    await expect(request).rejects.toMatchObject({ name: "AbortError" });
    mock.restore();
  });

  it("detecta respuestas no JSON", async () => {
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/records",
        respond: () => new Response("<html>error</html>", { status: 200 }),
      },
    ]);
    await expect(apiRequest("/records")).rejects.toMatchObject({
      code: "invalid_response",
    });
    mock.restore();
  });
});
