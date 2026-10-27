import type { Servidor } from "../types/api";

export interface FieldErrors {
  [field: string]: string;
}

export interface CoordinatesValidation {
  values: { latitud: number; longitud: number } | null;
  errors: FieldErrors;
}

function parseNumber(value: string): number | null {
  if (!value.trim()) return null;
  const normalized = value.replace(",", ".");
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

export function validateCoordinates(latText: string, lonText: string): CoordinatesValidation {
  const errors: FieldErrors = {};
  const lat = parseNumber(latText);
  const lon = parseNumber(lonText);

  if (lat === null) {
    errors.latitud = "Introduce una latitud numérica.";
  } else if (lat < -90 || lat > 90) {
    errors.latitud = "La latitud debe estar entre -90 y 90.";
  }

  if (lon === null) {
    errors.longitud = "Introduce una longitud numérica.";
  } else if (lon < -180 || lon > 180) {
    errors.longitud = "La longitud debe estar entre -180 y 180.";
  }

  if (Object.keys(errors).length > 0 || lat === null || lon === null) {
    return { values: null, errors };
  }
  return { values: { latitud: lat, longitud: lon }, errors };
}

export interface RecordFormValues {
  servidor: Servidor;
  nombre: string;
  paterno: string;
  materno: string;
  estado: string;
  municipio: string;
  latitud: string;
  longitud: string;
  temperatura: string;
  humedad: string;
  viento: string;
  fechaHoraLocal: string;
}

export interface RecordValidation {
  errors: FieldErrors;
  values: {
    servidor: Servidor;
    nombre: string;
    paterno: string | null;
    materno: string | null;
    estado: string;
    municipio: string;
    latitud: number;
    longitud: number;
    temperatura: number;
    humedad: number;
    viento: number;
    fecha_hora: string | null;
  } | null;
}

const CONTROL_CHARS = /[\u0000-\u001f\u007f]/;

function required(
  value: string,
  label: string,
  errors: FieldErrors,
  field: string,
  maxLength: number,
): string {
  const cleaned = value.trim();
  if (!cleaned) {
    errors[field] = `${label} es obligatorio.`;
  } else if (cleaned.length > maxLength) {
    errors[field] = `${label} no puede superar ${maxLength} caracteres.`;
  } else if (CONTROL_CHARS.test(cleaned)) {
    errors[field] = `${label} contiene caracteres no permitidos.`;
  }
  return cleaned;
}

function optional(
  value: string,
  label: string,
  errors: FieldErrors,
  field: string,
  maxLength: number,
): string | null {
  const cleaned = value.trim();
  if (!cleaned) return null;
  if (cleaned.length > maxLength) {
    errors[field] = `${label} no puede superar ${maxLength} caracteres.`;
  } else if (CONTROL_CHARS.test(cleaned)) {
    errors[field] = `${label} contiene caracteres no permitidos.`;
  }
  return cleaned;
}

function boundedNumber(
  raw: string,
  label: string,
  errors: FieldErrors,
  field: string,
  min: number,
  max: number,
  decimals?: number,
): number | null {
  const value = parseNumber(raw);
  if (value === null) {
    errors[field] = `${label} es obligatorio y debe ser numérico.`;
    return null;
  }
  if (value < min || value > max) {
    errors[field] = `${label} debe estar entre ${min} y ${max}.`;
    return null;
  }
  if (decimals !== undefined) {
    const factor = 10 ** decimals;
    if (Math.abs(value * factor - Math.round(value * factor)) > 1e-7) {
      errors[field] = `${label} admite como máximo ${decimals} decimales.`;
      return null;
    }
  }
  return value;
}

export function validateRecordForm(values: RecordFormValues): RecordValidation {
  const errors: FieldErrors = {};
  const nombre = required(values.nombre, "El nombre", errors, "nombre", 100);
  const estado = required(values.estado, "El estado", errors, "estado", 120);
  const municipio = required(values.municipio, "El municipio", errors, "municipio", 120);
  const paterno = optional(values.paterno, "El apellido paterno", errors, "paterno", 100);
  const materno = optional(values.materno, "El apellido materno", errors, "materno", 100);

  if (values.servidor === "windows" && !paterno) {
    errors.paterno = "El apellido paterno es obligatorio para SQL Server (Windows).";
  }

  const latitud = boundedNumber(
    values.latitud,
    "La latitud",
    errors,
    "latitud",
    -90,
    90,
    7,
  );
  const longitud = boundedNumber(
    values.longitud,
    "La longitud",
    errors,
    "longitud",
    -180,
    180,
    7,
  );
  const temperatura = boundedNumber(
    values.temperatura,
    "La temperatura",
    errors,
    "temperatura",
    -90,
    60,
    2,
  );
  const humedad = boundedNumber(
    values.humedad,
    "La humedad",
    errors,
    "humedad",
    0,
    100,
    2,
  );
  const viento = boundedNumber(values.viento, "El viento", errors, "viento", 0, 500, 2);

  let fechaHora: string | null = null;
  if (values.fechaHoraLocal.trim()) {
    const parsed = new Date(values.fechaHoraLocal);
    if (Number.isNaN(parsed.getTime())) {
      errors.fechaHoraLocal = "La fecha y hora no son válidas.";
    } else if (parsed.getUTCFullYear() < 1900) {
      errors.fechaHoraLocal = "La fecha debe ser posterior a 1900.";
    } else if (parsed.getTime() > Date.now() + 5 * 60 * 1000) {
      errors.fechaHoraLocal = "La fecha de observación no puede estar en el futuro.";
    } else {
      fechaHora = parsed.toISOString();
    }
  }

  if (
    Object.keys(errors).length > 0 ||
    latitud === null ||
    longitud === null ||
    temperatura === null ||
    humedad === null ||
    viento === null
  ) {
    return { errors, values: null };
  }

  return {
    errors,
    values: {
      servidor: values.servidor,
      nombre,
      paterno,
      materno,
      estado,
      municipio,
      latitud,
      longitud,
      temperatura,
      humedad,
      viento,
      fecha_hora: fechaHora,
    },
  };
}

export function isValidTotpFormat(code: string): boolean {
  return /^\d{6}$/.test(code);
}

const USERNAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$/;

export interface RegistrationFormValues {
  username: string;
  password: string;
  confirmPassword: string;
}

export interface RegistrationValidation {
  errors: FieldErrors;
  values: { username: string; password: string } | null;
}

function passwordClassCount(password: string): number {
  return [
    /[a-z]/.test(password),
    /[A-Z]/.test(password),
    /[0-9]/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ].filter(Boolean).length;
}

export function validateRegistration(
  values: RegistrationFormValues,
): RegistrationValidation {
  const errors: FieldErrors = {};
  const username = values.username.trim();
  const password = values.password;

  if (!username) {
    errors.username = "Introduce un nombre de usuario.";
  } else if (username.length < 3) {
    errors.username = "El nombre de usuario debe tener al menos 3 caracteres.";
  } else if (username.length > 64) {
    errors.username = "Máximo 64 caracteres.";
  } else if (!USERNAME_PATTERN.test(username)) {
    errors.username =
      "Usa letras, números, punto, guion o guion bajo; debe empezar por letra o número.";
  }

  if (!password) {
    errors.password = "Introduce una contraseña.";
  } else if (password.length < 12) {
    errors.password = "La contraseña debe tener al menos 12 caracteres.";
  } else if (password.length > 128) {
    errors.password = "La contraseña no puede superar 128 caracteres.";
  } else if (password !== password.trim()) {
    errors.password = "La contraseña no puede empezar ni terminar con espacios.";
  } else if (passwordClassCount(password) < 3) {
    errors.password =
      "Combina al menos tres tipos: minúsculas, mayúsculas, números y símbolos.";
  }

  if (!values.confirmPassword) {
    errors.confirmPassword = "Repite la contraseña.";
  } else if (values.confirmPassword !== password) {
    errors.confirmPassword = "Las contraseñas no coinciden.";
  }

  if (Object.keys(errors).length > 0) {
    return { errors, values: null };
  }
  return { errors, values: { username, password } };
}

export function mapAuthFieldErrors(
  details: Array<{ loc?: Array<string | number>; msg?: string }> | undefined,
): FieldErrors {
  const errors: FieldErrors = {};
  if (!details) return errors;
  for (const item of details) {
    const rawField = item.loc?.filter((part) => part !== "body").at(-1);
    if (
      (rawField === "username" || rawField === "password") &&
      item.msg
    ) {
      errors[rawField] = item.msg;
    }
  }
  return errors;
}

const API_FIELD_ALIASES: Record<string, string> = {
  fecha_hora: "fechaHoraLocal",
};

const RECORD_FIELDS = new Set([
  "servidor",
  "nombre",
  "paterno",
  "materno",
  "estado",
  "municipio",
  "latitud",
  "longitud",
  "temperatura",
  "humedad",
  "viento",
  "fechaHoraLocal",
]);

export function mapApiFieldErrors(
  details: Array<{ loc?: Array<string | number>; msg?: string }> | undefined,
): FieldErrors {
  const errors: FieldErrors = {};
  if (!details) return errors;
  for (const item of details) {
    const rawField = item.loc?.filter((part) => part !== "body").at(-1);
    if (typeof rawField !== "string" || !item.msg) continue;
    const field = API_FIELD_ALIASES[rawField] ?? rawField;
    if (RECORD_FIELDS.has(field)) {
      errors[field] = item.msg;
    }
  }
  return errors;
}
