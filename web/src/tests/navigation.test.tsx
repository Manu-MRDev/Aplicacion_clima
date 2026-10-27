import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { errorResponse, installFetchMock, jsonResponse } from "./http";
import { meResponse } from "./fixtures";
import { renderApp } from "./render";

describe("navegación y estructura accesible", () => {
  it("expone el menú principal, el destino actual y el enlace de salto", async () => {
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => jsonResponse(meResponse),
      },
    ]);
    renderApp(["/integrity"]);
    expect(
      await screen.findByRole("heading", { name: /verificación de integridad/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /saltar al contenido principal/i })).toHaveAttribute(
      "href",
      "#main-content",
    );
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    expect(screen.getByRole("navigation", { name: /navegación principal/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^panel$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^historial$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^nuevo registro$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^integridad$/i })).toHaveAttribute(
      "aria-current",
      "page",
    );
    mock.restore();
  });

  it("no guarda tokens ni secretos en el almacenamiento del navegador", async () => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => jsonResponse(meResponse),
      },
    ]);
    renderApp(["/"]);
    await screen.findByRole("heading", { name: /el clima, con contexto/i });
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(JSON.stringify(window.localStorage)).not.toContain("csrf-authenticated");
    mock.restore();
  });

  it("muestra una página 404 para rutas desconocidas", async () => {
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida"),
      },
    ]);
    renderApp(["/ruta-inexistente"]);
    expect(await screen.findByRole("heading", { name: /esta página no existe/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /ir al panel/i })).toBeInTheDocument();
    mock.restore();
  });

  it("muestra un estado de conexión si /auth/me falla con 5xx", async () => {
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => errorResponse(503, "unavailable", "Servicio temporalmente no disponible."),
      },
    ]);
    renderApp(["/"]);
    expect(
      await screen.findByRole("heading", { name: /no se pudo comprobar la sesión/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^reintentar$/i })).toBeInTheDocument();
    mock.restore();
  });
});
