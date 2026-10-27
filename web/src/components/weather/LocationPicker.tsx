import { useState, type FormEvent } from "react";

import { Crosshair, LocateFixed, MapPin, Send } from "lucide-react";

import { useGeolocation } from "../../hooks/useGeolocation";
import type { Coordinates, WeatherSelection } from "../../types/weather";
import { validateCoordinates } from "../../utils/validation";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Field } from "../ui/Field";

interface LocationPickerProps {
  loading: boolean;
  selection: WeatherSelection | null;
  onDeviceLocation: (coordinates: Coordinates) => void | Promise<void>;
  onManualLocation: (latitude: number, longitude: number) => void | Promise<void>;
}

export function LocationPicker({
  loading,
  selection,
  onDeviceLocation,
  onManualLocation,
}: LocationPickerProps) {
  const geolocation = useGeolocation();
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [errors, setErrors] = useState<{ latitud?: string; longitud?: string }>({});
  const busy = loading || geolocation.loading;

  const handleDevice = async () => {
    const coordinates = await geolocation.requestLocation();
    if (coordinates) {
      await onDeviceLocation(coordinates);
    }
  };

  const handleManual = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validation = validateCoordinates(latitude, longitude);
    setErrors(validation.errors);
    if (validation.values) {
      await onManualLocation(validation.values.latitud, validation.values.longitud);
    }
  };

  return (
    <Card className="location-picker" as="section">
      <div className="location-picker__current">
        <span className="location-picker__icon" aria-hidden="true">
          <MapPin size={20} />
        </span>
        <div>
          <p className="location-picker__label">Ubicación de la consulta</p>
          {selection ? (
            <>
              <strong>{locationTitle(selection)}</strong>
              <p className="small muted">
                {selection.coordinates.latitude.toFixed(5)},{" "}
                {selection.coordinates.longitude.toFixed(5)} ·{" "}
                {selection.source === "device"
                  ? "Ubicación del dispositivo"
                  : "Coordenadas seleccionadas"}
              </p>
            </>
          ) : (
            <strong className="muted">Todavía no has seleccionado una ubicación</strong>
          )}
        </div>
      </div>

      <div className="location-picker__actions">
        <Button
          variant="secondary"
          onClick={() => void handleDevice()}
          loading={geolocation.loading}
          loadingLabel="Obteniendo ubicación…"
          disabled={loading}
          icon={<LocateFixed aria-hidden="true" size={18} />}
        >
          {selection?.source === "device" ? "Actualizar mi ubicación" : "Usar mi ubicación"}
        </Button>
      </div>

      {geolocation.error ? (
        <Alert tone="warning" title="No se pudo usar la ubicación">
          {geolocation.errorMessage}
        </Alert>
      ) : null}

      <div className="location-picker__manual">
        <div className="location-picker__manual-title">
          <Crosshair aria-hidden="true" size={17} />
          <span>O consulta otras coordenadas</span>
        </div>
        <form
          className="coordinates-form"
          onSubmit={(event) => void handleManual(event)}
          noValidate
        >
          <Field id="manual-lat" label="Latitud" error={errors.latitud}>
            <input
              id="manual-lat"
              className="input"
              type="number"
              inputMode="decimal"
              min={-90}
              max={90}
              step="any"
              placeholder="19.4326"
              value={latitude}
              onChange={(event) => setLatitude(event.target.value)}
              aria-invalid={errors.latitud ? true : undefined}
              aria-describedby={errors.latitud ? "manual-lat-error" : undefined}
              disabled={busy}
            />
          </Field>
          <Field id="manual-lon" label="Longitud" error={errors.longitud}>
            <input
              id="manual-lon"
              className="input"
              type="number"
              inputMode="decimal"
              min={-180}
              max={180}
              step="any"
              placeholder="-99.1332"
              value={longitude}
              onChange={(event) => setLongitude(event.target.value)}
              aria-invalid={errors.longitud ? true : undefined}
              aria-describedby={errors.longitud ? "manual-lon-error" : undefined}
              disabled={busy}
            />
          </Field>
          <Button
            type="submit"
            loading={loading}
            loadingLabel="Consultando…"
            disabled={geolocation.loading}
            icon={<Send aria-hidden="true" size={17} />}
            className="coordinates-form__submit"
          >
            Consultar
          </Button>
        </form>
        <p className="small muted">
          La API no ofrece búsqueda por nombre de ciudad; introduce coordenadas en grados
          decimales. La geolocalización del navegador requiere HTTPS o localhost.
        </p>
      </div>
    </Card>
  );
}

export function locationTitle(selection: WeatherSelection): string {
  const location = selection.location;
  if (location) {
    const city = location.city || location.municipio;
    const parts = [city, location.municipio, location.estado].filter(
      (part, index, array) => Boolean(part) && array.indexOf(part) === index,
    );
    if (parts.length > 0) return parts.join(" · ");
    if (location.display_name) return location.display_name;
  }
  return `${selection.coordinates.latitude.toFixed(4)}, ${selection.coordinates.longitude.toFixed(4)}`;
}
