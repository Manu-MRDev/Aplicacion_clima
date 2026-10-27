import { useCallback, useEffect, useRef, useState } from "react";

import { getCurrentWeather, getReverseLocation } from "../services/weather";
import type { Coordinates, WeatherSelection } from "../types/weather";
import { errorMessage } from "../utils/errors";

export function useWeather() {
  const [selection, setSelection] = useState<WeatherSelection | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const load = useCallback(
    async (coordinates: Coordinates, source: "device" | "manual") => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      setLoading(true);
      setError(null);

      const [weatherResult, locationResult] = await Promise.allSettled([
        getCurrentWeather(coordinates.latitude, coordinates.longitude, controller.signal),
        getReverseLocation(coordinates.latitude, coordinates.longitude, controller.signal),
      ]);

      if (controller.signal.aborted) return;

      if (weatherResult.status === "rejected") {
        setLoading(false);
        setError(errorMessage(weatherResult.reason, "No se pudo consultar el clima."));
        return;
      }

      const location =
        locationResult.status === "fulfilled" ? locationResult.value : null;
      const locationError =
        locationResult.status === "rejected"
          ? errorMessage(
              locationResult.reason,
              "No se pudo identificar la localidad de estas coordenadas.",
            )
          : null;

      setSelection({
        coordinates,
        source,
        weather: weatherResult.value,
        location,
        locationError,
        updatedAt: new Date().toISOString(),
      });
      setLoading(false);
    },
    [],
  );

  const refresh = useCallback(async () => {
    if (!selection) return;
    await load(selection.coordinates, selection.source);
  }, [load, selection]);

  const clear = useCallback(() => {
    controllerRef.current?.abort();
    setSelection(null);
    setError(null);
    setLoading(false);
  }, []);

  useEffect(() => {
    return () => controllerRef.current?.abort();
  }, []);

  return { selection, loading, error, load, refresh, clear };
}
