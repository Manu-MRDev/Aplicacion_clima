export type Servidor = "ubuntu" | "windows";
export type ServidorQuery = Servidor | "ambos";
export type OrdenCampo = "fecha_hora" | "id";
export type Direccion = "asc" | "desc";

export interface ApiErrorDetail {
  code: string;
  message: string;
  request_id?: string;
  details?: {
    errors?: Array<{
      loc?: Array<string | number>;
      type?: string;
      msg?: string;
    }>;
  } | null;
}

export interface ApiErrorBody {
  error: ApiErrorDetail;
}

export interface Pagination {
  limit: number;
  offset: number;
  order: OrdenCampo;
  direction: Direccion;
  per_source: boolean;
}

export const SERVER_LABEL: Record<Servidor, string> = {
  ubuntu: "PostgreSQL · Ubuntu",
  windows: "SQL Server · Windows",
};
