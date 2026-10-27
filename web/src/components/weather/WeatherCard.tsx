import type { ReactNode } from "react";
import {
  CalendarClock,
  Clock3,
  Droplets,
  MapPin,
  Navigation,
  Thermometer,
  Wind,
} from "lucide-react";

import type { WeatherSelection } from "../../types/weather";
import { formatDateTime, formatNumber, formatTime, observedAtToUtc } from "../../utils/dates";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { WeatherIcon } from "./WeatherIcon";
import { locationTitle } from "./LocationPicker";

export function WeatherCard({ selection }: { selection: WeatherSelection }) {
  const { weather } = selection;
  const temperatureUnit = weather.units?.temperature || "°C";
  const humidityUnit = weather.units?.relative_humidity || "%";
  const windUnit = weather.units?.wind_speed || "km/h";
  const observedUtc = observedAtToUtc(weather);
  const condition = weather.condition || "Condición no informada";

  return (
    <Card className="weather-card" as="section">
      <div className="weather-card__hero">
        <div className="weather-card__main">
          <div className="weather-card__temperature">
            <span>
              {formatNumber(weather.temperature_c, 1)}
              <sup>{temperatureUnit}</sup>
            </span>
          </div>
          <div>
            <p className="weather-card__condition">
              <WeatherIcon
                code={weather.weather_code}
                known={weather.condition_known}
                size={30}
              />
              <strong>{condition}</strong>
            </p>
            <p className="weather-card__location">
              <MapPin aria-hidden="true" size={17} />
              {locationTitle(selection)}
            </p>
            <div className="cluster weather-card__badges">
              <Badge tone="info">
                {selection.source === "device"
                  ? "Ubicación del dispositivo"
                  : "Coordenadas seleccionadas"}
              </Badge>
              {!weather.condition_known ? (
                <Badge tone="warning">Código meteorológico desconocido</Badge>
              ) : null}
            </div>
          </div>
        </div>
        <div className="weather-card__art" aria-hidden="true">
          <WeatherIcon code={weather.weather_code} known={weather.condition_known} size={120} />
        </div>
      </div>

      <div className="weather-card__stats">
        <Stat
          icon={<Droplets size={20} />}
          label="Humedad relativa"
          value={`${formatNumber(weather.relative_humidity_pct, 0)} ${humidityUnit}`}
        />
        <Stat
          icon={<Wind size={20} />}
          label="Velocidad del viento"
          value={`${formatNumber(weather.wind_speed_kmh, 1)} ${windUnit}`}
        />
        <Stat
          icon={<Navigation size={20} />}
          label="Coordenadas"
          value={`${formatNumber(weather.coordinates.latitude, 5)}, ${formatNumber(
            weather.coordinates.longitude,
            5,
          )}`}
        />
        <Stat
          icon={<Clock3 size={20} />}
          label="Observación"
          value={formatDateTime(observedUtc, weather.timezone)}
          detail={weather.timezone ? `Zona: ${weather.timezone}` : undefined}
        />
        <Stat
          icon={<CalendarClock size={20} />}
          label="Última actualización"
          value={formatTime(selection.updatedAt)}
          detail={formatDateTime(selection.updatedAt)}
        />
        <Stat
          icon={<Thermometer size={20} />}
          label="Fuente"
          value={weather.provider || "Open-Meteo"}
          detail="Datos actuales"
        />
      </div>
    </Card>
  );
}

function Stat({
  icon,
  label,
  value,
  detail,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="weather-stat">
      <span className="weather-stat__icon" aria-hidden="true">
        {icon}
      </span>
      <div>
        <p className="weather-stat__label">{label}</p>
        <p className="weather-stat__value">{value}</p>
        {detail ? <p className="weather-stat__detail">{detail}</p> : null}
      </div>
    </div>
  );
}
