import { useNavigate } from "react-router-dom";

import {
  ArrowRight,
  BookmarkPlus,
  CloudSun,
  History,
  RefreshCw,
} from "lucide-react";

import { LocationPicker } from "../components/weather/LocationPicker";
import { WeatherCard } from "../components/weather/WeatherCard";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { CardSkeleton } from "../components/ui/Skeleton";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { useWeather } from "../hooks/useWeather";
import type { RecordPrefill } from "../types/records";
import { observedAtToUtc } from "../utils/dates";

export function DashboardPage() {
  const navigate = useNavigate();
  const { selection, loading, error, load, refresh } = useWeather();

  const handleSave = () => {
    if (!selection) return;
    const prefill: RecordPrefill = {
      estado: selection.location?.estado ?? "",
      municipio: selection.location?.municipio ?? selection.location?.city ?? "",
      latitud: selection.coordinates.latitude,
      longitud: selection.coordinates.longitude,
      temperatura: selection.weather.temperature_c,
      humedad: selection.weather.relative_humidity_pct,
      viento: selection.weather.wind_speed_kmh,
      fecha_hora: observedAtToUtc(selection.weather),
      locationLabel: selection.location?.display_name ?? undefined,
    };
    navigate("/records/new", { state: { prefill } });
  };

  return (
    <div className="container page">
      <PageHeader
        eyebrow="Panel meteorológico"
        title="El clima, con contexto"
        description="Consulta la condición actual y conserva la ubicación y las mediciones para un nuevo registro."
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => void refresh()}
              loading={loading}
              loadingLabel="Actualizando…"
              disabled={!selection}
              icon={<RefreshCw aria-hidden="true" size={17} />}
            >
              Actualizar
            </Button>
            <Button
              variant="secondary"
              onClick={() => navigate("/records")}
              icon={<History aria-hidden="true" size={17} />}
            >
              Historial
            </Button>
          </>
        }
      />

      <div className="dashboard-grid">
        <div className="dashboard-main stack-lg">
          <LocationPicker
            loading={loading}
            selection={selection}
            onDeviceLocation={(coordinates) =>
              void load(coordinates, "device")
            }
            onManualLocation={(latitude, longitude) =>
              void load({ latitude, longitude }, "manual")
            }
          />

          {error ? (
            <Alert
              tone="danger"
              title="No se pudo consultar el clima"
              actions={
                selection ? (
                  <Button variant="secondary" size="sm" onClick={() => void refresh()}>
                    Reintentar
                  </Button>
                ) : null
              }
              live
            >
              {error}
            </Alert>
          ) : null}

          {selection?.locationError ? (
            <Alert tone="warning" title="La localidad no pudo identificarse">
              {selection.locationError} Las coordenadas y el clima sí están disponibles.
            </Alert>
          ) : null}

          {loading && !selection ? (
            <div className="stack" aria-busy="true">
              <CardSkeleton />
              <div className="dashboard-stats-skeleton">
                <CardSkeleton />
                <CardSkeleton />
                <CardSkeleton />
              </div>
            </div>
          ) : selection ? (
            <div aria-busy={loading || undefined}>
              <WeatherCard selection={selection} />
            </div>
          ) : (
            <Card>
              <EmptyState
                icon={<CloudSun size={28} />}
                title="Selecciona una ubicación para empezar"
                description="Puedes usar la ubicación de tu dispositivo cuando concedas permiso o introducir coordenadas manualmente. No se mostrarán datos hasta consultar la API."
                action={
                  <Button
                    variant="secondary"
                    onClick={() => navigate("/records/new")}
                    icon={<BookmarkPlus aria-hidden="true" size={17} />}
                  >
                    Crear un registro manual
                  </Button>
                }
              />
            </Card>
          )}

          {selection ? (
            <Card className="dashboard-save">
              <div>
                <h2>Convertir esta consulta en un registro</h2>
                <p className="muted">
                  Los valores se copiarán al formulario para que los revises antes de
                  guardarlos en PostgreSQL o SQL Server. El usuario se toma de la sesión
                  autenticada.
                </p>
              </div>
              <Button
                onClick={handleSave}
                icon={<BookmarkPlus aria-hidden="true" size={18} />}
                iconAfter={<ArrowRight aria-hidden="true" size={18} />}
              >
                Guardar estos datos
              </Button>
            </Card>
          ) : null}
        </div>

        <aside className="dashboard-aside stack-lg" aria-label="Información de la consulta">
          <Card tone="soft" className="dashboard-note">
            <h2>Cómo funciona</h2>
            <ol className="step-list">
              <li>La API consulta Open-Meteo con las coordenadas elegidas.</li>
              <li>Nominatim identifica la localidad mediante geocodificación inversa.</li>
              <li>Puedes guardar la observación en uno de los dos servidores.</li>
              <li>La integridad se verifica después, desde el backend.</li>
            </ol>
          </Card>
          <Card className="dashboard-note">
            <h2>Privacidad de la ubicación</h2>
            <p className="muted small">
              La ubicación del dispositivo solo se solicita cuando pulsas “Usar mi
              ubicación”. No se guarda en el almacenamiento del navegador. Si prefieres no
              compartirla, introduce coordenadas manuales.
            </p>
          </Card>
          {selection ? (
            <Card className="dashboard-note">
              <h2>Atribución</h2>
              <p className="muted small">
                Datos meteorológicos: {selection.weather.provider || "Open-Meteo"}. 
                Geocodificación inversa: {selection.location?.attribution ?? "© OpenStreetMap contributors"}.
              </p>
            </Card>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
