import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { errorResponse, installFetchMock, jsonResponse } from "./http";
import { location, meResponse, weather } from "./fixtures";
import { renderApp } from "./render";

function baseRoutes() {
  return [
    {
      method: "GET",
      path: "/api/auth/me",
      respond: () => jsonResponse(meResponse),
    },
  ];
}

describe("panel meteorológico", () => {
  it("no consulta el clima automáticamente y permite coordenadas manuales", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      ...baseRoutes(),
      {
        method: "GET",
        path: "/api/weather/current",
        respond: () => jsonResponse(weather),
      },
      {
        method: "GET",
        path: "/api/locations/reverse",
        respond: () => jsonResponse(location),
      },
    ]);
    renderApp(["/"]);
    expect(
      await screen.findByRole("heading", { name: /el clima, con contexto/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/selecciona una ubicación para empezar/i)).toBeInTheDocument();
    expect(mock.callsFor("/api/weather/current")).toHaveLength(0);

    await user.type(screen.getByLabelText(/^latitud/i), "19.4326");
    await user.type(screen.getByLabelText(/^longitud/i), "-99.1332");
    await user.click(screen.getByRole("button", { name: /^consultar$/i }));

    expect(await screen.findByText(/principalmente despejado/i)).toBeInTheDocument();
    expect(screen.getByText(/21[.,]5/)).toBeInTheDocument();
    expect(screen.getAllByText(/coyoacán/i).length).toBeGreaterThan(0);
    expect(mock.callsFor("/api/weather/current")[0].url.searchParams.get("lat")).toBe(
      "19.4326",
    );
    expect(mock.callsFor("/api/weather/current")[0].url.searchParams.get("lon")).toBe(
      "-99.1332",
    );
    mock.restore();
  });

  it("permite usar la ubicación del dispositivo", async () => {
    const original = Object.getOwnPropertyDescriptor(navigator, "geolocation");
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: {
        getCurrentPosition: (
          success: (position: {
            coords: { latitude: number; longitude: number };
          }) => void,
        ) =>
          success({
            coords: { latitude: 19.4326, longitude: -99.1332 },
          }),
      },
    });
    const user = userEvent.setup();
    const mock = installFetchMock([
      ...baseRoutes(),
      {
        method: "GET",
        path: "/api/weather/current",
        respond: () => jsonResponse(weather),
      },
      {
        method: "GET",
        path: "/api/locations/reverse",
        respond: () => jsonResponse(location),
      },
    ]);
    renderApp(["/"]);
    await screen.findByRole("heading", { name: /el clima, con contexto/i });
    await user.click(screen.getByRole("button", { name: /usar mi ubicación/i }));
    expect(await screen.findByText(/principalmente despejado/i)).toBeInTheDocument();
    expect(
      screen.getByText(/ubicación del dispositivo/i, { selector: ".badge" }),
    ).toBeInTheDocument();
    if (original) Object.defineProperty(navigator, "geolocation", original);
    else Reflect.deleteProperty(navigator, "geolocation");
    mock.restore();
  });

  it("explica el rechazo de permiso de ubicación y no inventa datos", async () => {
    const original = Object.getOwnPropertyDescriptor(navigator, "geolocation");
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: {
        getCurrentPosition: (
          _success: unknown,
          failure: (error: { code: number; PERMISSION_DENIED: number }) => void,
        ) => failure({ code: 1, PERMISSION_DENIED: 1 }),
      },
    });
    const user = userEvent.setup();
    const mock = installFetchMock(baseRoutes());
    renderApp(["/"]);
    await screen.findByRole("heading", { name: /el clima, con contexto/i });
    await user.click(screen.getByRole("button", { name: /usar mi ubicación/i }));
    expect(await screen.findByText(/no se concedió permiso/i)).toBeInTheDocument();
    expect(screen.queryByText(/principalmente despejado/i)).not.toBeInTheDocument();
    if (original) Object.defineProperty(navigator, "geolocation", original);
    else Reflect.deleteProperty(navigator, "geolocation");
    mock.restore();
  });

  it("muestra el error del clima sin descartar la selección previa", async () => {
    const user = userEvent.setup();
    let weatherCalls = 0;
    const mock = installFetchMock([
      ...baseRoutes(),
      {
        method: "GET",
        path: "/api/weather/current",
        respond: () => {
          weatherCalls += 1;
          return weatherCalls === 1
            ? jsonResponse(weather)
            : errorResponse(502, "upstream_error", "El servicio meteorológico no respondió.");
        },
      },
      {
        method: "GET",
        path: "/api/locations/reverse",
        respond: () => jsonResponse(location),
      },
    ]);
    renderApp(["/"]);
    await screen.findByRole("heading", { name: /el clima, con contexto/i });
    await user.type(screen.getByLabelText(/^latitud/i), "19.4326");
    await user.type(screen.getByLabelText(/^longitud/i), "-99.1332");
    await user.click(screen.getByRole("button", { name: /^consultar$/i }));
    await screen.findByText(/principalmente despejado/i);
    await user.click(screen.getByRole("button", { name: /^actualizar$/i }));
    expect(await screen.findByText(/servicio meteorológico no respondió/i)).toBeInTheDocument();
    expect(screen.getByText(/principalmente despejado/i)).toBeInTheDocument();
    mock.restore();
  });

  it("precarga el formulario de registro con los datos reales consultados", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      ...baseRoutes(),
      {
        method: "GET",
        path: "/api/weather/current",
        respond: () => jsonResponse(weather),
      },
      {
        method: "GET",
        path: "/api/locations/reverse",
        respond: () => jsonResponse(location),
      },
    ]);
    renderApp(["/"]);
    await screen.findByRole("heading", { name: /el clima, con contexto/i });
    await user.type(screen.getByLabelText(/^latitud/i), "19.4326");
    await user.type(screen.getByLabelText(/^longitud/i), "-99.1332");
    await user.click(screen.getByRole("button", { name: /^consultar$/i }));
    await screen.findByText(/principalmente despejado/i);
    await user.click(screen.getByRole("button", { name: /guardar estos datos/i }));
    expect(
      await screen.findByRole("heading", { name: /guardar una observación/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/^latitud/i)).toHaveValue(19.4326);
    expect(screen.getByLabelText(/^longitud/i)).toHaveValue(-99.1332);
    expect(screen.getByLabelText(/^temperatura/i)).toHaveValue(21.5);
    expect(screen.getByLabelText(/^humedad/i)).toHaveValue(55);
    expect(screen.getByLabelText(/^viento/i)).toHaveValue(12.3);
    expect(screen.getByLabelText(/^estado/i)).toHaveValue("Ciudad de México");
    expect(screen.getByLabelText(/^municipio/i)).toHaveValue("Coyoacán");
    expect(mock.callsFor("/api/records")).toHaveLength(0);
    mock.restore();
  });

  it("muestra advertencia si falla la geocodificación pero conserva el clima", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      ...baseRoutes(),
      {
        method: "GET",
        path: "/api/weather/current",
        respond: () => jsonResponse(weather),
      },
      {
        method: "GET",
        path: "/api/locations/reverse",
        respond: () =>
          errorResponse(502, "upstream_error", "No se pudo identificar la localidad."),
      },
    ]);
    renderApp(["/"]);
    await screen.findByRole("heading", { name: /el clima, con contexto/i });
    await user.type(screen.getByLabelText(/^latitud/i), "19.4326");
    await user.type(screen.getByLabelText(/^longitud/i), "-99.1332");
    await user.click(screen.getByRole("button", { name: /^consultar$/i }));
    expect(await screen.findByText(/la localidad no pudo identificarse/i)).toBeInTheDocument();
    expect(screen.getByText(/principalmente despejado/i)).toBeInTheDocument();
    mock.restore();
  });

  it("maneja una respuesta incompleta sin fabricar valores", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      ...baseRoutes(),
      {
        method: "GET",
        path: "/api/weather/current",
        respond: () =>
          jsonResponse({
            ...weather,
            temperature_c: null,
            relative_humidity_pct: null,
            wind_speed_kmh: null,
            condition_known: false,
          }),
      },
      {
        method: "GET",
        path: "/api/locations/reverse",
        respond: () => jsonResponse(location),
      },
    ]);
    renderApp(["/"]);
    await screen.findByRole("heading", { name: /el clima, con contexto/i });
    await user.type(screen.getByLabelText(/^latitud/i), "19.4326");
    await user.type(screen.getByLabelText(/^longitud/i), "-99.1332");
    await user.click(screen.getByRole("button", { name: /^consultar$/i }));
    expect(
      await screen.findByText(/código meteorológico desconocido/i),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    });
    mock.restore();
  });
});
