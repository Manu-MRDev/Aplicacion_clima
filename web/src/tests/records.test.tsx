import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { errorResponse, installFetchMock, jsonResponse } from "./http";
import { meResponse, recordUbuntu, recordsResponse } from "./fixtures";
import { renderApp } from "./render";

function routes(recordsHandler = () => jsonResponse(recordsResponse)) {
  return [
    {
      method: "GET",
      path: "/api/auth/me",
      respond: () => jsonResponse(meResponse),
    },
    {
      method: "GET",
      path: "/api/records",
      respond: recordsHandler,
    },
    {
      method: "GET",
      path: "/api/records/7",
      respond: () => jsonResponse(recordUbuntu),
    },
  ];
}

describe("historial de registros", () => {
  it("consulta ambos servidores y distingue el origen de cada fila", async () => {
    const mock = installFetchMock(routes());
    renderApp(["/records"]);
    expect(
      await screen.findByRole("heading", { name: /registros climáticos/i }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("cell", { name: /^ana$/i })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: /^luis$/i })).toBeInTheDocument();
    expect(screen.getAllByText("PostgreSQL · Ubuntu").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SQL Server · Windows").length).toBeGreaterThan(0);
    const request = mock.callsFor("/api/records")[0];
    expect(request.url.searchParams.get("servidor")).toBe("ambos");
    expect(request.url.searchParams.get("limit")).toBe("25");
    expect(request.url.searchParams.get("orden")).toBe("fecha_hora");
    expect(request.url.searchParams.get("direccion")).toBe("desc");
    mock.restore();
  });

  it("abre el detalle por ID y servidor", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock(routes());
    renderApp(["/records"]);
    await screen.findByRole("cell", { name: /^ana$/i });
    await user.click(
      screen.getByRole("button", {
        name: /ver detalle del registro 7 de postgresql/i,
      }),
    );
    const dialog = await screen.findByRole("dialog", { name: /registro #7/i });
    expect(within(dialog).getByText("Ana Pérez López")).toBeInTheDocument();
    expect(within(dialog).getByText("19.4326")).toBeInTheDocument();
    expect(mock.callsFor("/api/records/7")[0].url.searchParams.get("servidor")).toBe(
      "ubuntu",
    );
    mock.restore();
  });

  it("aplica filtros de servidor y usuario", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock(routes());
    renderApp(["/records"]);
    await screen.findByRole("cell", { name: /^ana$/i });
    const serverSelect = screen.getByLabelText(/^servidor$/i);
    await user.selectOptions(serverSelect, "windows");
    await user.type(screen.getByLabelText(/usuario exacto/i), "luis");
    await user.click(screen.getByRole("button", { name: /aplicar filtros/i }));
    await waitFor(() => {
      const requests = mock.callsFor("/api/records");
      expect(requests.length).toBeGreaterThan(1);
      expect(requests.at(-1)?.url.searchParams.get("servidor")).toBe("windows");
      expect(requests.at(-1)?.url.searchParams.get("usuario")).toBe("luis");
      expect(requests.at(-1)?.url.searchParams.get("offset")).toBe("0");
    });
    mock.restore();
  });

  it("ordena por ID y alterna la dirección", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock(routes());
    renderApp(["/records"]);
    await screen.findByRole("cell", { name: /^ana$/i });
    const idHeader = screen.getByRole("button", { name: /^id$/i });
    await user.click(idHeader);
    await waitFor(() => {
      expect(mock.callsFor("/api/records").at(-1)?.url.searchParams.get("orden")).toBe(
        "id",
      );
      expect(
        mock.callsFor("/api/records").at(-1)?.url.searchParams.get("direccion"),
      ).toBe("desc");
    });
    await screen.findByRole("button", { name: /^id$/i });
    await user.click(screen.getByRole("button", { name: /^id$/i }));
    await waitFor(() => {
      expect(
        mock.callsFor("/api/records").at(-1)?.url.searchParams.get("direccion"),
      ).toBe("asc");
    });
    mock.restore();
  });

  it("pagina con el desplazamiento por fuente", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock(
      routes(() =>
        jsonResponse({
          ...recordsResponse,
          fuentes: {
            ubuntu: { status: "ok", count: 1, has_more: true },
            windows: { status: "ok", count: 1, has_more: true },
          },
        }),
      ),
    );
    renderApp(["/records"]);
    await screen.findByRole("cell", { name: /^ana$/i });
    await user.click(screen.getByRole("button", { name: /^siguiente$/i }));
    await waitFor(() => {
      expect(mock.callsFor("/api/records").at(-1)?.url.searchParams.get("offset")).toBe(
        "25",
      );
    });
    expect(screen.getByRole("button", { name: /^anterior$/i })).toBeEnabled();
    mock.restore();
  });

  it("informa resultados parciales sin ocultar la fuente disponible", async () => {
    const mock = installFetchMock(
      routes(() =>
        jsonResponse({
          ...recordsResponse,
          registros: [recordUbuntu],
          fuentes: {
            ubuntu: { status: "ok", count: 1, has_more: false },
            windows: {
              status: "error",
              count: 0,
              has_more: false,
              error: "database_unavailable",
            },
          },
          parcial: true,
        }),
      ),
    );
    renderApp(["/records"]);
    expect(await screen.findByText(/resultados parciales/i)).toBeInTheDocument();
    expect(screen.getByText(/base de datos no disponible/i)).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: /^ana$/i })).toBeInTheDocument();
    mock.restore();
  });

  it("muestra un estado vacío cuando no hay coincidencias", async () => {
    const mock = installFetchMock(
      routes(() =>
        jsonResponse({
          ...recordsResponse,
          registros: [],
          fuentes: {
            ubuntu: { status: "ok", count: 0, has_more: false },
            windows: { status: "ok", count: 0, has_more: false },
          },
        }),
      ),
    );
    renderApp(["/records"]);
    expect(
      await screen.findByText(/no existen registros con estos filtros/i),
    ).toBeInTheDocument();
    mock.restore();
  });

  it("muestra el error 503 sin inventar filas", async () => {
    const mock = installFetchMock(
      routes(() =>
        errorResponse(503, "database_unavailable", "Los servidores de datos no están disponibles."),
      ),
    );
    renderApp(["/records"]);
    expect(
      await screen.findByText(/no se pudo consultar el historial/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    mock.restore();
  });

  it("no conserva filas de una consulta anterior si la nueva falla", async () => {
    const user = userEvent.setup();
    let calls = 0;
    const mock = installFetchMock(
      routes(() => {
        calls += 1;
        return calls === 1
          ? jsonResponse(recordsResponse)
          : errorResponse(503, "database_unavailable", "La consulta nueva falló.");
      }),
    );
    renderApp(["/records"]);
    await screen.findByRole("cell", { name: /^ana$/i });
    await user.selectOptions(screen.getByLabelText(/^servidor$/i), "windows");
    await user.click(screen.getByRole("button", { name: /aplicar filtros/i }));
    expect(await screen.findByText(/la consulta nueva falló/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    mock.restore();
  });
});
