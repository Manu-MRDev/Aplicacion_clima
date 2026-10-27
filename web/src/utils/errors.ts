import { ApiError } from "../services/apiClient";

export function errorMessage(error: unknown, fallback = "No fue posible completar la operación."): string {
  if (error instanceof ApiError) {
    if (error.retryAfter) {
      return `${error.message} Reintenta en ${error.retryAfter} s.`;
    }
    return error.message;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export const SOURCE_STATUS_LABEL: Record<string, string> = {
  ok: "Consultado",
  unavailable: "No disponible",
  error: "Error",
  empty: "Sin datos",
};

export const INTEGRITY_STATUS_LABEL: Record<string, string> = {
  ok: "Cadena válida",
  empty: "Sin bloques todavía",
  invalid: "Inconsistencias detectadas",
  partial: "Verificación parcial",
  unavailable: "No disponible",
  disabled: "Integridad deshabilitada",
  error: "Error de consulta",
};

export type VisualTone = "success" | "warning" | "danger" | "neutral" | "info";

export function integrityTone(status: string): VisualTone {
  switch (status) {
    case "ok":
      return "success";
    case "empty":
      return "info";
    case "invalid":
      return "danger";
    case "partial":
      return "warning";
    case "disabled":
    case "unavailable":
      return "neutral";
    default:
      return "danger";
  }
}
