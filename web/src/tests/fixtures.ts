import type { MeResponse } from "../types/auth";
import type { CurrentWeather, ReverseLocation } from "../types/weather";
import type {
  CreateRecordResponse,
  RecordsListResponse,
  WeatherRecord,
} from "../types/records";
import type { IntegrityVerifyResponse } from "../types/integrity";

export const meResponse: MeResponse = {
  user: {
    id: 1,
    username: "ana",
    totp_enabled: true,
    created_at: "2025-01-01T00:00:00Z",
  },
  csrf_token: "csrf-authenticated",
  session_expires_at: "2026-10-25T23:00:00Z",
};

export const weather: CurrentWeather = {
  coordinates: { latitude: 19.4326, longitude: -99.1332 },
  temperature_c: 21.5,
  relative_humidity_pct: 55,
  wind_speed_kmh: 12.3,
  weather_code: 1,
  condition: "Principalmente despejado",
  condition_known: true,
  observed_at: "2026-10-25T12:30",
  timezone: "America/Mexico_City",
  utc_offset_seconds: -21600,
  units: {
    temperature: "°C",
    relative_humidity: "%",
    wind_speed: "km/h",
  },
  provider: "open-meteo",
};

export const location: ReverseLocation = {
  coordinates: { latitude: 19.4326, longitude: -99.1332 },
  city: "Ciudad de México",
  municipio: "Coyoacán",
  estado: "Ciudad de México",
  pais: "México",
  country_code: "mx",
  display_name: "Coyoacán, Ciudad de México, México",
  provider: "nominatim",
  attribution: "© OpenStreetMap contributors",
};

export const recordUbuntu: WeatherRecord = {
  id: 7,
  servidor: "ubuntu",
  usuario: "ana",
  nombre: "Ana",
  paterno: "Pérez",
  materno: "López",
  estado: "Ciudad de México",
  municipio: "Coyoacán",
  latitud: 19.4326,
  longitud: -99.1332,
  temperatura: 21.5,
  humedad: 55,
  viento: 12.3,
  fecha_hora: "2026-10-25T18:30:00Z",
};

export const recordWindows: WeatherRecord = {
  ...recordUbuntu,
  id: 7,
  servidor: "windows",
  usuario: "luis",
  nombre: "Luis",
  paterno: "García",
  fecha_hora: "2026-10-24T17:00:00Z",
};

export const recordsResponse: RecordsListResponse = {
  servidor: "ambos",
  registros: [recordUbuntu, recordWindows],
  paginacion: {
    limit: 25,
    offset: 0,
    order: "fecha_hora",
    direction: "desc",
    per_source: true,
  },
  fuentes: {
    ubuntu: { status: "ok", count: 1, has_more: false },
    windows: { status: "ok", count: 1, has_more: false },
  },
  parcial: false,
};

export const createResponse: CreateRecordResponse = {
  registro: recordUbuntu,
  integridad: {
    status: "created",
    cadena: "api-ubuntu",
    indice: 3,
    hash_actual: "a".repeat(64),
    detalle: null,
  },
};

export const integrityResponse: IntegrityVerifyResponse = {
  status: "ok",
  servidor: "ambos",
  sources: {
    ubuntu: {
      servidor: "ubuntu",
      status: "ok",
      bloques_verificados: 3,
      registros_verificados: 3,
      registros_sin_bloque: 12,
      errores: [],
      advertencias: ["12 registro(s) sin bloque de integridad"],
      detalle: null,
    },
    windows: {
      servidor: "windows",
      status: "ok",
      bloques_verificados: 2,
      registros_verificados: 2,
      registros_sin_bloque: 0,
      errores: [],
      advertencias: [],
      detalle: null,
    },
  },
};
