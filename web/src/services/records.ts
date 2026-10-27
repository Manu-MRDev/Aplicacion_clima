import { apiRequest } from "./apiClient";
import type {
  CreateRecordResponse,
  RecordCreateInput,
  RecordsListResponse,
  RecordsQuery,
  WeatherRecord,
} from "../types/records";
import type { Servidor } from "../types/api";

function recordsQueryParams(query: RecordsQuery) {
  return {
    servidor: query.servidor,
    usuario: query.usuario?.trim() || undefined,
    desde: query.desde || undefined,
    hasta: query.hasta || undefined,
    limit: query.limit,
    offset: query.offset,
    orden: query.orden,
    direccion: query.direccion,
  };
}

export function listRecords(query: RecordsQuery, signal?: AbortSignal) {
  return apiRequest<RecordsListResponse>("/records", {
    query: recordsQueryParams(query),
    signal,
  });
}

export function createRecord(
  input: RecordCreateInput,
  csrfToken: string,
  signal?: AbortSignal,
) {
  return apiRequest<CreateRecordResponse>("/records", {
    method: "POST",
    body: input,
    csrfToken,
    signal,
  });
}

export function getRecord(
  id: number,
  servidor: Servidor,
  signal?: AbortSignal,
) {
  return apiRequest<WeatherRecord>(`/records/${id}`, {
    query: { servidor },
    signal,
  });
}
