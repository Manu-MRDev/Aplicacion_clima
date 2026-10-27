import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { errorResponse, installFetchMock, jsonResponse } from "./http";
import { integrityResponse, meResponse } from "./fixtures";
import { renderApp } from "./render";

function routes(handler = () => jsonResponse(integrityResponse)) {
  return [
    {
      method: "GET",
      path: "/api/auth/me",
      respond: () => jsonResponse(meResponse),
    },
    {
      method: "GET",
      path: "/api/integrity/verify",
      respond: handler,
    },
  ];
}

describe("verificación de integridad", () => {
  it("empieza en estado neutral y no verifica automáticamente", async () => {
    const mock = installFetchMock(routes());
    renderApp(["/integrity"]);
    expect(
      await screen.findByRole("heading", { name: /verificación de integridad/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/aún no se ha ejecutado la verificación/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/cadena válida/i)).not.toBeInTheDocument();
    expect(mock.callsFor("/api/integrity/verify")).toHaveLength(0);
    mock.restore();
  });

  it("muestra el resultado real de ambas cadenas", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock(routes());
    renderApp(["/integrity"]);
    await screen.findByRole("heading", { name: /verificación de integridad/i });
    await user.click(screen.getByRole("button", { name: /ejecutar verificación/i }));
    expect(await screen.findByText(/resultado global/i)).toBeInTheDocument();
    expect(screen.getAllByText("Cadena válida").length).toBeGreaterThan(0);
    expect(screen.getAllByText("PostgreSQL · Ubuntu").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SQL Server · Windows").length).toBeGreaterThan(0);
    expect(screen.getByText(/12 registro\(s\) sin bloque de integridad/i)).toBeInTheDocument();
    expect(mock.callsFor("/api/integrity/verify")[0].url.searchParams.get("servidor")).toBe(
      "ambos",
    );
    mock.restore();
  });

  it("permite verificar solo un servidor", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock(routes());
    renderApp(["/integrity"]);
    await screen.findByRole("heading", { name: /verificación de integridad/i });
    await user.click(screen.getByRole("radio", { name: /^SQL Server · Windows/i }));
    await user.click(screen.getByRole("button", { name: /ejecutar verificación/i }));
    await waitFor(() => {
      expect(
        mock.callsFor("/api/integrity/verify")[0].url.searchParams.get("servidor"),
      ).toBe("windows");
    });
    mock.restore();
  });

  it("presenta inconsistencias como error, no como éxito", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock(
      routes(() =>
        jsonResponse({
          ...integrityResponse,
          status: "invalid",
          sources: {
            ubuntu: {
              servidor: "ubuntu",
              status: "invalid",
              bloques_verificados: 3,
              registros_verificados: 3,
              registros_sin_bloque: 0,
              errores: ["Bloque 2: hash anterior no coincide"],
              advertencias: [],
              detalle: null,
            },
          },
        }),
      ),
    );
    renderApp(["/integrity"]);
    await screen.findByRole("heading", { name: /verificación de integridad/i });
    await user.click(screen.getByRole("button", { name: /ejecutar verificación/i }));
    expect(
      await screen.findByRole("heading", { name: /inconsistencias detectadas/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/hash anterior no coincide/i)).toBeInTheDocument();
    expect(screen.queryByText(/sin errores ni advertencias/i)).not.toBeInTheDocument();
    mock.restore();
  });

  it("señala una verificación parcial y la fuente no disponible", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock(
      routes(() =>
        jsonResponse({
          ...integrityResponse,
          status: "partial",
          sources: {
            ubuntu: integrityResponse.sources.ubuntu,
            windows: {
              servidor: "windows",
              status: "unavailable",
              bloques_verificados: 0,
              registros_verificados: 0,
              registros_sin_bloque: 0,
              errores: [],
              advertencias: [],
              detalle: "Base de datos no disponible",
            },
          },
        }),
      ),
    );
    renderApp(["/integrity"]);
    await screen.findByRole("heading", { name: /verificación de integridad/i });
    await user.click(screen.getByRole("button", { name: /ejecutar verificación/i }));
    expect(
      await screen.findByRole("heading", { name: /verificación parcial/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/no todas las fuentes pudieron verificarse/i)).toBeInTheDocument();
    expect(screen.getAllByText(/no disponible/i).length).toBeGreaterThan(0);
    mock.restore();
  });

  it("distingue una cadena vacía de una cadena válida", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock(
      routes(() =>
        jsonResponse({
          ...integrityResponse,
          status: "empty",
          sources: {
            ubuntu: {
              ...integrityResponse.sources.ubuntu,
              status: "empty",
              bloques_verificados: 0,
              registros_verificados: 0,
              errores: [],
              advertencias: [],
            },
          },
          servidor: "ubuntu",
        }),
      ),
    );
    renderApp(["/integrity"]);
    await screen.findByRole("heading", { name: /verificación de integridad/i });
    await user.click(screen.getByRole("button", { name: /ejecutar verificación/i }));
    expect(
      await screen.findByRole("heading", { name: /sin bloques todavía/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/todavía no hay bloques nuevos/i)).toBeInTheDocument();
    mock.restore();
  });

  it("muestra un error de consulta y permite reintentar", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock(
      routes(() =>
        errorResponse(503, "database_unavailable", "La verificación no está disponible."),
      ),
    );
    renderApp(["/integrity"]);
    await screen.findByRole("heading", { name: /verificación de integridad/i });
    await user.click(screen.getByRole("button", { name: /ejecutar verificación/i }));
    expect(await screen.findByText(/no se pudo verificar/i)).toBeInTheDocument();
    expect(screen.getByText(/la verificación no está disponible/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^reintentar$/i })).toBeInTheDocument();
    mock.restore();
  });
});
