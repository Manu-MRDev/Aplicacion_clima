import { apiRequest } from "./apiClient";
import type { ServidorQuery } from "../types/api";
import type { IntegrityVerifyResponse } from "../types/integrity";

export function verifyIntegrity(servidor: ServidorQuery, signal?: AbortSignal) {
  return apiRequest<IntegrityVerifyResponse>("/integrity/verify", {
    query: { servidor },
    signal,
  });
}
