import { describe, expect, it } from "vitest";

import {
  isValidTotpFormat,
  mapAuthFieldErrors,
  validateCoordinates,
  validateRecordForm,
  validateRegistration,
  type RecordFormValues,
} from "../utils/validation";

const baseValues: RecordFormValues = {
  servidor: "ubuntu",
  nombre: "Ana",
  paterno: "Pérez",
  materno: "López",
  estado: "Ciudad de México",
  municipio: "Coyoacán",
  latitud: "19.4326",
  longitud: "-99.1332",
  temperatura: "21.5",
  humedad: "55",
  viento: "12.3",
  fechaHoraLocal: "",
};

describe("validateCoordinates", () => {
  it("acepta coordenadas válidas", () => {
    expect(validateCoordinates("19.43", "-99.13")).toEqual({
      values: { latitud: 19.43, longitud: -99.13 },
      errors: {},
    });
  });

  it("rechaza coordenadas fuera de rango", () => {
    const result = validateCoordinates("91", "-181");
    expect(result.values).toBeNull();
    expect(result.errors.latitud).toContain("entre -90 y 90");
    expect(result.errors.longitud).toContain("entre -180 y 180");
  });

  it("rechaza valores no numéricos", () => {
    const result = validateCoordinates("abc", "");
    expect(result.errors.latitud).toBeTruthy();
    expect(result.errors.longitud).toBeTruthy();
  });
});

describe("validateRecordForm", () => {
  it("acepta un formulario completo", () => {
    const result = validateRecordForm(baseValues);
    expect(result.errors).toEqual({});
    expect(result.values).toMatchObject({
      nombre: "Ana",
      latitud: 19.4326,
      humedad: 55,
      viento: 12.3,
    });
  });

  it("exige nombre, estado y municipio", () => {
    const result = validateRecordForm({
      ...baseValues,
      nombre: "",
      estado: "",
      municipio: "",
    });
    expect(result.errors.nombre).toBeTruthy();
    expect(result.errors.estado).toBeTruthy();
    expect(result.errors.municipio).toBeTruthy();
    expect(result.values).toBeNull();
  });

  it("exige apellido paterno para SQL Server", () => {
    const result = validateRecordForm({
      ...baseValues,
      servidor: "windows",
      paterno: "",
    });
    expect(result.errors.paterno).toContain("obligatorio");
  });

  it("valida rangos de mediciones", () => {
    const result = validateRecordForm({
      ...baseValues,
      temperatura: "80",
      humedad: "120",
      viento: "-1",
    });
    expect(result.errors.temperatura).toBeTruthy();
    expect(result.errors.humedad).toBeTruthy();
    expect(result.errors.viento).toBeTruthy();
  });

  it("rechaza fechas futuras", () => {
    const future = new Date(Date.now() + 60 * 60 * 1000);
    const local = future.toISOString().slice(0, 16);
    const result = validateRecordForm({ ...baseValues, fechaHoraLocal: local });
    expect(result.errors.fechaHoraLocal).toContain("futuro");
  });

  it("convierte la fecha local a ISO UTC", () => {
    const result = validateRecordForm({
      ...baseValues,
      fechaHoraLocal: "2026-10-25T12:30",
    });
    expect(result.values?.fecha_hora).toContain("T");
    expect(result.values?.fecha_hora).toContain("Z");
  });
});

describe("validateRegistration", () => {
  const valid = {
    username: "nueva.cuenta",
    password: "Clave-Segura-2026!",
    confirmPassword: "Clave-Segura-2026!",
  };

  it("acepta un alta válida y no envía la confirmación", () => {
    expect(validateRegistration(valid)).toEqual({
      errors: {},
      values: { username: "nueva.cuenta", password: "Clave-Segura-2026!" },
    });
  });

  it("rechaza usuarios inválidos", () => {
    expect(validateRegistration({ ...valid, username: "a" }).errors.username).toContain(
      "al menos 3",
    );
    expect(
      validateRegistration({ ...valid, username: "con espacio" }).errors.username,
    ).toContain("Usa letras");
  });

  it("rechaza contraseñas débiles y confirmaciones distintas", () => {
    const result = validateRegistration({
      ...valid,
      password: "corta",
      confirmPassword: "otra",
    });
    expect(result.errors.password).toContain("al menos 12");
    expect(result.errors.confirmPassword).toContain("no coinciden");
    expect(result.values).toBeNull();
  });

  it("mapea errores de autenticación del backend", () => {
    expect(
      mapAuthFieldErrors([
        { loc: ["body", "username"], msg: "nombre inválido" },
        { loc: ["body", "password"], msg: "contraseña inválida" },
        { loc: ["body", "extra"], msg: "no permitido" },
      ]),
    ).toEqual({
      username: "nombre inválido",
      password: "contraseña inválida",
    });
  });
});

describe("isValidTotpFormat", () => {
  it("solo acepta seis dígitos", () => {
    expect(isValidTotpFormat("123456")).toBe(true);
    expect(isValidTotpFormat("12345")).toBe(false);
    expect(isValidTotpFormat("12345a")).toBe(false);
  });
});
