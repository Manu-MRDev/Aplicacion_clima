import { useCallback, useEffect, useRef, useState } from "react";

import { listRecords } from "../services/records";
import type { RecordsListResponse, RecordsQuery } from "../types/records";
import { errorMessage } from "../utils/errors";

export function useRecords(query: RecordsQuery, reloadToken: number) {
  const [data, setData] = useState<RecordsListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError(null);
    // Evita mostrar filas de una consulta anterior con los filtros nuevos.
    setData(null);
    try {
      const response = await listRecords(query, controller.signal);
      if (!controller.signal.aborted) {
        setData(response);
      }
    } catch (loadError) {
      if (!controller.signal.aborted) {
        setError(
          errorMessage(loadError, "No se pudo consultar el historial de registros."),
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [query]);

  useEffect(() => {
    void load();
  }, [load, reloadToken]);

  useEffect(() => {
    return () => controllerRef.current?.abort();
  }, []);

  return { data, loading, error, reload: load };
}
