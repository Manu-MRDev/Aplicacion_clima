import { useCallback, useEffect, useRef, useState } from "react";

import type { Coordinates } from "../types/weather";

export type GeolocationErrorCode =
  | "unsupported"
  | "denied"
  | "unavailable"
  | "timeout"
  | "invalid";

export interface GeolocationState {
  loading: boolean;
  error: GeolocationErrorCode | null;
  errorMessage: string | null;
  coordinates: Coordinates | null;
}

const MESSAGES: Record<GeolocationErrorCode, string> = {
  unsupported: "Este navegador no permite obtener la ubicación.",
  denied: "No se concedió permiso para usar la ubicación. Puedes introducir coordenadas manualmente.",
  unavailable: "La ubicación no está disponible en este momento.",
  timeout: "La solicitud de ubicación tardó demasiado. Intenta de nuevo.",
  invalid: "El navegador devolvió coordenadas no válidas.",
};

export function useGeolocation() {
  const [state, setState] = useState<GeolocationState>({
    loading: false,
    error: null,
    errorMessage: null,
    coordinates: null,
  });
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const requestLocation = useCallback(async (): Promise<Coordinates | null> => {
    if (!("geolocation" in navigator)) {
      setState({
        loading: false,
        error: "unsupported",
        errorMessage: MESSAGES.unsupported,
        coordinates: null,
      });
      return null;
    }

    setState((current) => ({
      ...current,
      loading: true,
      error: null,
      errorMessage: null,
    }));

    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          if (!mounted.current) {
            resolve(null);
            return;
          }
          const latitude = position.coords.latitude;
          const longitude = position.coords.longitude;
          if (
            !Number.isFinite(latitude) ||
            !Number.isFinite(longitude) ||
            latitude < -90 ||
            latitude > 90 ||
            longitude < -180 ||
            longitude > 180
          ) {
            setState({
              loading: false,
              error: "invalid",
              errorMessage: MESSAGES.invalid,
              coordinates: null,
            });
            resolve(null);
            return;
          }
          const coordinates = { latitude, longitude };
          setState({
            loading: false,
            error: null,
            errorMessage: null,
            coordinates,
          });
          resolve(coordinates);
        },
        (error) => {
          if (!mounted.current) {
            resolve(null);
            return;
          }
          const code: GeolocationErrorCode =
            error.code === error.PERMISSION_DENIED
              ? "denied"
              : error.code === error.POSITION_UNAVAILABLE
                ? "unavailable"
                : "timeout";
          setState({
            loading: false,
            error: code,
            errorMessage: MESSAGES[code],
            coordinates: null,
          });
          resolve(null);
        },
        { enableHighAccuracy: false, timeout: 12_000, maximumAge: 60_000 },
      );
    });
  }, []);

  return { ...state, requestLocation };
}
