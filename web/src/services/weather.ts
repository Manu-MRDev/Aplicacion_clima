import { apiRequest } from "./apiClient";
import type { CurrentWeather, ReverseLocation } from "../types/weather";

export function getCurrentWeather(lat: number, lon: number, signal?: AbortSignal) {
  return apiRequest<CurrentWeather>("/weather/current", {
    query: { lat, lon },
    signal,
    suppressAuthEvent: true,
  });
}

export function getReverseLocation(lat: number, lon: number, signal?: AbortSignal) {
  return apiRequest<ReverseLocation>("/locations/reverse", {
    query: { lat, lon },
    signal,
    suppressAuthEvent: true,
  });
}
