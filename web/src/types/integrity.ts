import type { ServidorQuery } from "./api";

export interface IntegritySourceReport {
  servidor: string;
  status: string;
  bloques_verificados: number;
  registros_verificados: number;
  registros_sin_bloque: number;
  errores: string[];
  advertencias: string[];
  detalle: string | null;
}

export interface IntegrityVerifyResponse {
  status: string;
  servidor: ServidorQuery;
  sources: Record<string, IntegritySourceReport>;
}
