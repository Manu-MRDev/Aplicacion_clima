import type {
  Direccion,
  OrdenCampo,
  Pagination,
  Servidor,
  ServidorQuery,
} from "./api";

export interface WeatherRecord {
  id: number;
  servidor: string;
  usuario: string;
  nombre: string;
  paterno: string | null;
  materno: string | null;
  estado: string;
  municipio: string;
  latitud: number | null;
  longitud: number | null;
  temperatura: number | null;
  humedad: number | null;
  viento: number | null;
  fecha_hora: string | null;
}

export interface RecordCreateInput {
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
  fecha_hora?: string | null;
}

export interface IntegrityInfo {
  status: "created" | "disabled" | "unavailable";
  cadena: string;
  indice: number | null;
  hash_actual: string | null;
  detalle: string | null;
}

export interface CreateRecordResponse {
  registro: WeatherRecord;
  integridad: IntegrityInfo;
}

export interface SourceStatus {
  status: string;
  count: number;
  has_more: boolean;
  error?: string | null;
}

export interface RecordsListResponse {
  servidor: ServidorQuery;
  registros: WeatherRecord[];
  paginacion: Pagination;
  fuentes: Record<string, SourceStatus>;
  parcial: boolean;
}

export interface RecordsQuery {
  servidor: ServidorQuery;
  usuario?: string;
  desde?: string;
  hasta?: string;
  limit: number;
  offset: number;
  orden: OrdenCampo;
  direccion: Direccion;
}

export interface RecordPrefill {
  estado?: string;
  municipio?: string;
  latitud: number;
  longitud: number;
  temperatura: number;
  humedad: number;
  viento: number;
  fecha_hora?: string | null;
  locationLabel?: string;
}
