export interface Coordinates {
  latitude: number;
  longitude: number;
}

export interface WeatherUnits {
  temperature: string;
  relative_humidity: string;
  wind_speed: string;
}

export interface CurrentWeather {
  coordinates: Coordinates;
  temperature_c: number;
  relative_humidity_pct: number;
  wind_speed_kmh: number;
  weather_code: number;
  condition: string;
  condition_known: boolean;
  observed_at: string;
  timezone: string;
  utc_offset_seconds: number | null;
  units: WeatherUnits;
  provider: string;
}

export interface ReverseLocation {
  coordinates: Coordinates;
  city: string | null;
  municipio: string | null;
  estado: string | null;
  pais: string | null;
  country_code: string | null;
  display_name: string | null;
  provider: string;
  attribution: string;
}

export interface WeatherSelection {
  coordinates: Coordinates;
  source: "device" | "manual";
  weather: CurrentWeather;
  location: ReverseLocation | null;
  locationError: string | null;
  updatedAt: string;
}
