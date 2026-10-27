import { afterEach, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { errorResponse, installFetchMock, jsonResponse } from "./http";
import { createResponse, meResponse } from "./fixtures";
import { renderApp } from "./render";

function authRoute() {
  return {
    method: "GET",
    path: "/api/auth/me",
    respond: () => jsonResponse(meResponse),
  };
}

async function fillRequiredFields(
  user: ReturnType<typeof userEvent.setup>,
  options: { paterno?: boolean } = {},
) {
  await user.type(screen.getByLabelText(/^nombre/i), "Ana");
  if (options.paterno !== false) {
    await user.type(screen.getByLabelText(/^apellido paterno/i), "Pérez");
  }
  await user.type(screen.getByLabelText(/^estado/i), "Ciudad de México");
  await user.type(screen.getByLabelText(/^municipio/i), "Coyoacán");
  await user.clear(screen.getByLabelText(/^latitud/i));
  await user.type(screen.getByLabelText(/^latitud/i), "19.4326");
  await user.clear(screen.getByLabelText(/^longitud/i));
  await user.type(screen.getByLabelText(/^longitud/i), "-99.1332");
  await user.type(screen.getByLabelText(/temperatura/i), "21.5");
  await user.type(screen.getByLabelText(/humedad/i), "55");
  await user.type(screen.getByLabelText(/viento/i), "12.3");
}

const originalSpeechRecognition = Object.getOwnPropertyDescriptor(
  window,
  "SpeechRecognition",
);

afterEach(() => {
  if (originalSpeechRecognition) {
    Object.defineProperty(window, "SpeechRecognition", originalSpeechRecognition);
  } else {
    Reflect.deleteProperty(window, "SpeechRecognition");
  }
  Reflect.deleteProperty(window, "webkitSpeechRecognition");
});

describe("formulario de registro", () => {
  it("valida los campos obligatorios antes de abrir la confirmación", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([authRoute()]);
    renderApp(["/records/new"]);
    await screen.findByRole("heading", { name: /guardar una observación/i });
    await user.click(screen.getByRole("button", { name: /revisar y guardar/i }));
    expect(await screen.findByText(/revisa los siguientes campos/i)).toBeInTheDocument();
    expect(screen.getAllByText(/el nombre es obligatorio/i).length).toBeGreaterThan(0);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mock.callsFor("/api/records")).toHaveLength(0);
    mock.restore();
  });

  it("exige apellido paterno al elegir SQL Server (Windows)", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([authRoute()]);
    renderApp(["/records/new"]);
    await screen.findByRole("heading", { name: /guardar una observación/i });
    const windowsRadio = screen.getByRole("radio", { name: /sql server/i });
    await user.click(windowsRadio);
    expect(windowsRadio).toBeChecked();
    await fillRequiredFields(user, { paterno: false });
    expect(screen.getByText(/destino seleccionado:/i)).toHaveTextContent("SQL Server");
    await user.click(screen.getByRole("button", { name: /revisar y guardar/i }));
    expect(
      screen.getAllByText(/apellido paterno es obligatorio para sql server/i).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    mock.restore();
  });

  it("confirma el servidor y crea el registro sin enviar usuario", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      authRoute(),
      {
        method: "POST",
        path: "/api/records",
        respond: () => jsonResponse(createResponse, 201),
      },
    ]);
    renderApp(["/records/new"]);
    await screen.findByRole("heading", { name: /guardar una observación/i });
    await fillRequiredFields(user);
    await user.click(screen.getByRole("button", { name: /revisar y guardar/i }));
    const dialog = await screen.findByRole("dialog", { name: /confirmar guardado/i });
    expect(within(dialog).getByText("PostgreSQL · Ubuntu")).toBeInTheDocument();
    expect(within(dialog).getByText("ana")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: /guardar registro/i }));
    expect(
      await screen.findByRole("heading", { name: /la observación se guardó/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /registro #7/i })).toBeInTheDocument();
    expect(screen.getByText(/integridad confirmada/i)).toBeInTheDocument();
    const post = mock.callsFor("/api/records")[0];
    expect(post.headers.get("X-CSRF-Token")).toBe("csrf-authenticated");
    expect(post.body).toMatchObject({
      servidor: "ubuntu",
      nombre: "Ana",
      paterno: "Pérez",
      estado: "Ciudad de México",
      municipio: "Coyoacán",
      latitud: 19.4326,
      longitud: -99.1332,
      temperatura: 21.5,
      humedad: 55,
      viento: 12.3,
    });
    expect(post.body).not.toHaveProperty("usuario");
    mock.restore();
  });

  it("envía el destino Windows cuando se selecciona el servidor 2", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      authRoute(),
      {
        method: "POST",
        path: "/api/records",
        respond: () =>
          jsonResponse(
            {
              ...createResponse,
              registro: { ...createResponse.registro, servidor: "windows" },
              integridad: { ...createResponse.integridad, cadena: "api-windows" },
            },
            201,
          ),
      },
    ]);
    renderApp(["/records/new"]);
    await screen.findByRole("heading", { name: /guardar una observación/i });
    await user.click(screen.getByRole("radio", { name: /sql server/i }));
    await fillRequiredFields(user);
    await user.click(screen.getByRole("button", { name: /revisar y guardar/i }));
    const dialog = await screen.findByRole("dialog", { name: /confirmar guardado/i });
    expect(within(dialog).getByText("SQL Server · Windows")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: /guardar registro/i }));
    await screen.findByRole("heading", { name: /la observación se guardó/i });
    expect(mock.callsFor("/api/records")[0].body).toMatchObject({
      servidor: "windows",
      paterno: "Pérez",
    });
    mock.restore();
  });

  it("advierte cuando la integridad no pudo confirmarse", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      authRoute(),
      {
        method: "POST",
        path: "/api/records",
        respond: () =>
          jsonResponse(
            {
              ...createResponse,
              integridad: {
                status: "disabled",
                cadena: "api-ubuntu",
                indice: null,
                hash_actual: null,
                detalle: null,
              },
            },
            201,
          ),
      },
    ]);
    renderApp(["/records/new"]);
    await screen.findByRole("heading", { name: /guardar una observación/i });
    await fillRequiredFields(user);
    await user.click(screen.getByRole("button", { name: /revisar y guardar/i }));
    const dialog = await screen.findByRole("dialog", { name: /confirmar guardado/i });
    await user.click(within(dialog).getByRole("button", { name: /guardar registro/i }));
    expect(
      await screen.findByText(/integridad está deshabilitada en ese servidor/i),
    ).toBeInTheDocument();
    mock.restore();
  });

  it("mantiene el formulario y explica un fallo del servidor", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      authRoute(),
      {
        method: "POST",
        path: "/api/records",
        respond: () =>
          errorResponse(503, "database_unavailable", "La base de datos no está disponible."),
      },
    ]);
    renderApp(["/records/new"]);
    await screen.findByRole("heading", { name: /guardar una observación/i });
    await fillRequiredFields(user);
    await user.click(screen.getByRole("button", { name: /revisar y guardar/i }));
    const dialog = await screen.findByRole("dialog", { name: /confirmar guardado/i });
    await user.click(within(dialog).getByRole("button", { name: /guardar registro/i }));
    expect(await screen.findByText(/no se guardó el registro/i)).toBeInTheDocument();
    expect(screen.getByText(/base de datos no está disponible/i)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /guardar una observación/i }),
    ).toBeInTheDocument();
    mock.restore();
  });

  it("asocia los errores 422 del backend con los campos visibles", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      authRoute(),
      {
        method: "POST",
        path: "/api/records",
        respond: () =>
          errorResponse(422, "validation_error", "Los datos enviados no son válidos", {
            details: {
              errors: [
                {
                  loc: ["body", "fecha_hora"],
                  type: "value_error",
                  msg: "La fecha no puede estar en el futuro.",
                },
              ],
            },
          }),
      },
    ]);
    renderApp(["/records/new"]);
    await screen.findByRole("heading", { name: /guardar una observación/i });
    await fillRequiredFields(user);
    await user.click(screen.getByRole("button", { name: /revisar y guardar/i }));
    const dialog = await screen.findByRole("dialog", { name: /confirmar guardado/i });
    await user.click(within(dialog).getByRole("button", { name: /guardar registro/i }));
    expect(
      await screen.findByText(/el backend rechazó algunos datos/i),
    ).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /la fecha no puede estar en el futuro/i });
    expect(link).toHaveAttribute("href", "#record-fechaHoraLocal");
    expect(screen.getByLabelText(/fecha y hora local/i)).toHaveAttribute(
      "aria-describedby",
      "record-fechaHoraLocal-hint record-fechaHoraLocal-error",
    );
    mock.restore();
  });

  it("usa el comando de voz únicamente para preparar el guardado", async () => {
    class FakeSpeechRecognition {
      lang = "";
      continuous = false;
      interimResults = false;
      maxAlternatives = 1;
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      onstart: (() => void) | null = null;
      start() {
        window.setTimeout(() => {
          this.onstart?.();
          this.onresult?.({
            results: [
              Object.assign([{ transcript: "guardar en servidor 2" }], {
                isFinal: true,
              }),
            ],
          });
        }, 0);
      }
      stop() {
        this.onend?.();
      }
      abort() {
        this.onend?.();
      }
    }
    Object.defineProperty(window, "SpeechRecognition", {
      configurable: true,
      value: FakeSpeechRecognition,
    });

    const user = userEvent.setup();
    const mock = installFetchMock([authRoute()]);
    renderApp(["/records/new"]);
    await screen.findByRole("heading", { name: /guardar una observación/i });
    await fillRequiredFields(user);
    await user.click(screen.getByRole("button", { name: /dictar comando/i }));
    await waitFor(() => {
      expect(screen.getByText(/se preparó el guardado en sql server/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("radio", { name: /sql server/i })).toBeChecked();
    expect(await screen.findByRole("dialog", { name: /confirmar guardado/i })).toBeInTheDocument();
    expect(mock.callsFor("/api/records")).toHaveLength(0);
    mock.restore();
  });

  it("no interpreta comandos de clima como guardado", async () => {
    class FakeSpeechRecognition {
      lang = "";
      continuous = false;
      interimResults = false;
      maxAlternatives = 1;
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      onstart: (() => void) | null = null;
      start() {
        window.setTimeout(() => {
          this.onstart?.();
          this.onresult?.({
            results: [
              Object.assign([{ transcript: "consultar el clima" }], {
                isFinal: true,
              }),
            ],
          });
        }, 0);
      }
      stop() {
        this.onend?.();
      }
      abort() {
        this.onend?.();
      }
    }
    Object.defineProperty(window, "SpeechRecognition", {
      configurable: true,
      value: FakeSpeechRecognition,
    });
    const user = userEvent.setup();
    const mock = installFetchMock([authRoute()]);
    renderApp(["/records/new"]);
    await screen.findByRole("heading", { name: /guardar una observación/i });
    await user.click(screen.getByRole("button", { name: /dictar comando/i }));
    expect(
      await screen.findByText(/no reconocí un comando para guardar/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    mock.restore();
  });
});
