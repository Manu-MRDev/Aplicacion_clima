import { describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { errorResponse, installFetchMock, jsonResponse } from "./http";
import { meResponse } from "./fixtures";
import { renderApp } from "./render";

const enrollmentResponse = {
  manual_key: "JBSWY3DPEHPK3PXP",
  otpauth_uri: "otpauth://totp/Clima:ana?secret=JBSWY3DPEHPK3PXP",
  qr_data_uri: "data:image/png;base64,AAAA",
  issuer: "Clima API",
  account: "ana",
  expires_at: "2026-10-25T22:30:00Z",
  message: "Escanee el código QR",
};

const authenticatedResponse = {
  status: "authenticated",
  user: meResponse.user,
  csrf_token: "csrf-after-totp",
  session_expires_at: "2026-10-26T06:00:00Z",
};

const registrationResponse = {
  status: "enrollment_required",
  csrf_token: "csrf-register",
  expires_at: "2026-10-25T22:30:00Z",
  message: "Cuenta creada. Configure el segundo factor antes de continuar.",
};

describe("flujo de autenticación", () => {
  it("muestra el formulario de credenciales cuando no hay sesión", async () => {
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida o expirada"),
      },
    ]);
    renderApp(["/login"]);
    expect(
      await screen.findByRole("heading", { name: /inicia sesión/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/nombre de usuario/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^contraseña/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /mostrar contraseña/i })).toBeInTheDocument();
    mock.restore();
  });

  it("muestra el segundo factor tras validar credenciales", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida"),
      },
      {
        method: "POST",
        path: "/api/auth/login",
        respond: () =>
          jsonResponse({
            status: "totp_required",
            csrf_token: "csrf-pending",
            expires_at: "2026-10-25T22:30:00Z",
            message: "Introduzca el código",
          }),
      },
    ]);
    renderApp(["/login"]);
    await screen.findByRole("heading", { name: /inicia sesión/i });
    await user.type(screen.getByLabelText(/nombre de usuario/i), "ana");
    await user.type(screen.getByLabelText(/^contraseña/i), "secreto");
    await user.click(screen.getByRole("button", { name: /^continuar$/i }));
    expect(
      await screen.findByRole("heading", { name: /verificación en dos pasos/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/ana/)).toBeInTheDocument();
    expect(mock.calls[0].url.pathname).toBe("/api/auth/me");
    expect(mock.callsFor("/api/auth/login")).toHaveLength(1);
    mock.restore();
  });

  it("informa credenciales incorrectas sin crear sesión", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida"),
      },
      {
        method: "POST",
        path: "/api/auth/login",
        respond: () =>
          errorResponse(401, "unauthorized", "Credenciales inválidas o sesión no válida"),
      },
    ]);
    renderApp(["/login"]);
    await screen.findByRole("heading", { name: /inicia sesión/i });
    await user.type(screen.getByLabelText(/nombre de usuario/i), "ana");
    await user.type(screen.getByLabelText(/^contraseña/i), "mal");
    await user.click(screen.getByRole("button", { name: /^continuar$/i }));
    expect(await screen.findByText(/credenciales inválidas/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /panel/i })).not.toBeInTheDocument();
    mock.restore();
  });

  it("rechaza localmente un código TOTP incompleto y muestra el error del backend", async () => {
    const user = userEvent.setup();
    let verifyCalls = 0;
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida"),
      },
      {
        method: "POST",
        path: "/api/auth/login",
        respond: () =>
          jsonResponse({
            status: "totp_required",
            csrf_token: "csrf-pending",
            expires_at: "2026-10-25T22:30:00Z",
            message: "Introduzca el código",
          }),
      },
      {
        method: "POST",
        path: "/api/auth/totp/verify",
        respond: () => {
          verifyCalls += 1;
          return errorResponse(401, "unauthorized", "Código de verificación inválido");
        },
      },
    ]);
    renderApp(["/login"]);
    await screen.findByRole("heading", { name: /inicia sesión/i });
    await user.type(screen.getByLabelText(/nombre de usuario/i), "ana");
    await user.type(screen.getByLabelText(/^contraseña/i), "secreto");
    await user.click(screen.getByRole("button", { name: /^continuar$/i }));
    const codeInput = await screen.findByLabelText(/código de verificación/i);
    expect(screen.getByRole("button", { name: /verificar y entrar/i })).toBeDisabled();
    await user.type(codeInput, "123");
    expect(verifyCalls).toBe(0);
    await user.type(codeInput, "456");
    await user.click(screen.getByRole("button", { name: /verificar y entrar/i }));
    expect(await screen.findByText(/código de verificación inválido/i)).toBeInTheDocument();
    expect(verifyCalls).toBe(1);
    expect(codeInput).toHaveValue("");
    mock.restore();
  });

  it("completa el TOTP y entra al panel", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida"),
      },
      {
        method: "POST",
        path: "/api/auth/login",
        respond: () =>
          jsonResponse({
            status: "totp_required",
            csrf_token: "csrf-pending",
            expires_at: "2026-10-25T22:30:00Z",
            message: "Introduzca el código",
          }),
      },
      {
        method: "POST",
        path: "/api/auth/totp/verify",
        respond: () => jsonResponse(authenticatedResponse),
      },
    ]);
    renderApp(["/login"]);
    await screen.findByRole("heading", { name: /inicia sesión/i });
    await user.type(screen.getByLabelText(/nombre de usuario/i), "ana");
    await user.type(screen.getByLabelText(/^contraseña/i), "secreto");
    await user.click(screen.getByRole("button", { name: /^continuar$/i }));
    await user.type(await screen.findByLabelText(/código de verificación/i), "123456");
    await user.click(screen.getByRole("button", { name: /verificar y entrar/i }));
    expect(
      await screen.findByRole("heading", { name: /el clima, con contexto/i }),
    ).toBeInTheDocument();
    expect(mock.callsFor("/api/auth/totp/verify")[0].headers.get("X-CSRF-Token")).toBe(
      "csrf-pending",
    );
    mock.restore();
  });

  it("muestra la inscripción QR y confirma el autenticador", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida"),
      },
      {
        method: "POST",
        path: "/api/auth/login",
        respond: () =>
          jsonResponse({
            status: "enrollment_required",
            csrf_token: "csrf-enroll",
            expires_at: "2026-10-25T22:30:00Z",
            message: "Debe configurar el segundo factor",
          }),
      },
      {
        method: "POST",
        path: "/api/auth/totp/enroll",
        respond: () => jsonResponse(enrollmentResponse),
      },
      {
        method: "POST",
        path: "/api/auth/totp/confirm",
        respond: () => jsonResponse(authenticatedResponse),
      },
    ]);
    renderApp(["/login"]);
    await screen.findByRole("heading", { name: /inicia sesión/i });
    await user.type(screen.getByLabelText(/nombre de usuario/i), "ana");
    await user.type(screen.getByLabelText(/^contraseña/i), "secreto");
    await user.click(screen.getByRole("button", { name: /^continuar$/i }));
    expect(
      await screen.findByRole("heading", { name: /configura tu autenticador/i }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /generar código qr/i }));
    expect(await screen.findByAltText(/código qr de inscripción/i)).toBeInTheDocument();
    expect(screen.getByText("JBSWY3DPEHPK3PXP")).toBeInTheDocument();
    await user.type(
      screen.getByLabelText(/código generado por la aplicación/i),
      "123456",
    );
    await user.click(screen.getByRole("button", { name: /confirmar y entrar/i }));
    expect(
      await screen.findByRole("heading", { name: /el clima, con contexto/i }),
    ).toBeInTheDocument();
    expect(mock.callsFor("/api/auth/totp/enroll")[0].headers.get("X-CSRF-Token")).toBe(
      "csrf-enroll",
    );
    mock.restore();
  });

  it("redirige al login cuando una petición privada devuelve 401", async () => {
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => jsonResponse(meResponse),
      },
      {
        method: "GET",
        path: "/api/records",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida o expirada"),
      },
    ]);
    renderApp(["/records"]);
    expect(await screen.findByText(/la sesión terminó/i)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /inicia sesión/i }),
    ).toBeInTheDocument();
    mock.restore();
  });

  it("cierra la sesión mediante el endpoint real", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => jsonResponse(meResponse),
      },
      {
        method: "POST",
        path: "/api/auth/logout",
        respond: () => jsonResponse({ status: "logged_out" }),
      },
    ]);
    renderApp(["/"]);
    expect(
      await screen.findByRole("heading", { name: /el clima, con contexto/i }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /cerrar sesión/i }));
    const dialog = await screen.findByRole("dialog", { name: /cerrar sesión/i });
    await user.click(within(dialog).getByRole("button", { name: /cerrar sesión/i }));
    expect(
      await screen.findByRole("heading", { name: /inicia sesión/i }),
    ).toBeInTheDocument();
    expect(mock.callsFor("/api/auth/logout")[0].headers.get("X-CSRF-Token")).toBe(
      "csrf-authenticated",
    );
    mock.restore();
  });

  it("alterna la visibilidad de la contraseña", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida"),
      },
    ]);
    renderApp(["/login"]);
    const password = await screen.findByLabelText(/^contraseña/i);
    expect(password).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: /mostrar contraseña/i }));
    expect(password).toHaveAttribute("type", "text");
    await user.click(screen.getByRole("button", { name: /ocultar contraseña/i }));
    expect(password).toHaveAttribute("type", "password");
    mock.restore();
  });

  it("permite abrir el formulario de registro desde el login", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida"),
      },
    ]);
    renderApp(["/login"]);
    await screen.findByRole("heading", { name: /inicia sesión/i });
    await user.click(screen.getByRole("link", { name: /crear una cuenta/i }));
    expect(
      await screen.findByRole("heading", { name: /crea tu cuenta/i }),
    ).toBeInTheDocument();
    mock.restore();
  });

  it("crea una cuenta y continúa con la inscripción TOTP", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida"),
      },
      {
        method: "POST",
        path: "/api/auth/register",
        respond: () => jsonResponse(registrationResponse, 201),
      },
      {
        method: "POST",
        path: "/api/auth/totp/enroll",
        respond: () => jsonResponse(enrollmentResponse),
      },
      {
        method: "POST",
        path: "/api/auth/totp/confirm",
        respond: () => jsonResponse(authenticatedResponse),
      },
    ]);
    renderApp(["/register"]);
    await screen.findByRole("heading", { name: /crea tu cuenta/i });
    await user.type(screen.getByLabelText(/nombre de usuario/i), "nueva");
    await user.type(screen.getByLabelText(/^contraseña/i), "Clave-Nueva-2026");
    await user.type(
      screen.getByLabelText(/repite la contraseña/i),
      "Clave-Nueva-2026",
    );
    await user.click(screen.getByRole("button", { name: /^crear cuenta$/i }));

    expect(
      await screen.findByRole("heading", { name: /configura tu autenticador/i }),
    ).toBeInTheDocument();
    const registerCall = mock.callsFor("/api/auth/register")[0];
    expect(registerCall.body).toEqual({
      username: "nueva",
      password: "Clave-Nueva-2026",
    });
    expect(registerCall.headers.get("X-CSRF-Token")).toBeNull();

    await user.click(screen.getByRole("button", { name: /generar código qr/i }));
    await user.type(
      screen.getByLabelText(/código generado por la aplicación/i),
      "123456",
    );
    await user.click(screen.getByRole("button", { name: /confirmar y entrar/i }));
    expect(
      await screen.findByRole("heading", { name: /el clima, con contexto/i }),
    ).toBeInTheDocument();
    expect(mock.callsFor("/api/auth/totp/enroll")[0].headers.get("X-CSRF-Token")).toBe(
      "csrf-register",
    );
    mock.restore();
  });

  it("muestra el conflicto cuando el nombre de usuario ya existe", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida"),
      },
      {
        method: "POST",
        path: "/api/auth/register",
        respond: () =>
          errorResponse(409, "conflict", "El nombre de usuario ya está en uso"),
      },
    ]);
    renderApp(["/register"]);
    await screen.findByRole("heading", { name: /crea tu cuenta/i });
    await user.type(screen.getByLabelText(/nombre de usuario/i), "ana");
    await user.type(screen.getByLabelText(/^contraseña/i), "Clave-Nueva-2026");
    await user.type(
      screen.getByLabelText(/repite la contraseña/i),
      "Clave-Nueva-2026",
    );
    await user.click(screen.getByRole("button", { name: /^crear cuenta$/i }));
    expect(await screen.findByText(/ya está en uso/i)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /crea tu cuenta/i }),
    ).toBeInTheDocument();
    mock.restore();
  });

  it("valida localmente la contraseña y la confirmación antes de enviar", async () => {
    const user = userEvent.setup();
    const mock = installFetchMock([
      {
        method: "GET",
        path: "/api/auth/me",
        respond: () => errorResponse(401, "unauthorized", "Sesión no válida"),
      },
    ]);
    renderApp(["/register"]);
    await screen.findByRole("heading", { name: /crea tu cuenta/i });
    await user.type(screen.getByLabelText(/nombre de usuario/i), "nueva");
    await user.type(screen.getByLabelText(/^contraseña/i), "corta");
    await user.type(screen.getByLabelText(/repite la contraseña/i), "distinta");
    await user.click(screen.getByRole("button", { name: /^crear cuenta$/i }));

    expect(screen.getByText(/al menos 12 caracteres/i)).toBeInTheDocument();
    expect(screen.getByText(/las contraseñas no coinciden/i)).toBeInTheDocument();
    expect(mock.callsFor("/api/auth/register")).toHaveLength(0);
    mock.restore();
  });
});
