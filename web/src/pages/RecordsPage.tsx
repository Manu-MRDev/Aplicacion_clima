import { useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  Database,
  History,
  PlusCircle,
  RefreshCw,
  Server,
  TriangleAlert,
} from "lucide-react";

import { RecordDetailDialog } from "../components/records/RecordDetailDialog";
import { RecordsFilters } from "../components/records/RecordsFilters";
import { RecordTable } from "../components/records/RecordTable";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { LoadingBlock } from "../components/ui/Spinner";
import { useRecords } from "../hooks/useRecords";
import type { OrdenCampo, Servidor } from "../types/api";
import { SERVER_LABEL } from "../types/api";
import type { RecordsQuery, WeatherRecord } from "../types/records";
import { SOURCE_STATUS_LABEL } from "../utils/errors";

const DEFAULT_QUERY: RecordsQuery = {
  servidor: "ambos",
  limit: 25,
  offset: 0,
  orden: "fecha_hora",
  direccion: "desc",
};

export function RecordsPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState<RecordsQuery>(DEFAULT_QUERY);
  const [reloadToken, setReloadToken] = useState(0);
  const [selected, setSelected] = useState<WeatherRecord | null>(null);
  const { data, loading, error } = useRecords(query, reloadToken);

  const failedSources = data
    ? Object.entries(data.fuentes).filter(([, source]) => source.status !== "ok")
    : [];
  const canNext = data
    ? Object.values(data.fuentes).some((source) => source.has_more)
    : false;

  const handleSort = (field: OrdenCampo) => {
    setQuery((current) => ({
      ...current,
      offset: 0,
      orden: field,
      direccion:
        current.orden === field
          ? current.direccion === "desc"
            ? "asc"
            : "desc"
          : "desc",
    }));
  };

  const handlePage = (delta: number) => {
    setQuery((current) => ({
      ...current,
      offset: Math.max(0, current.offset + delta * current.limit),
    }));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="container page">
      <PageHeader
        eyebrow="Historial"
        title="Registros climáticos"
        description="Consulta las observaciones de PostgreSQL (Ubuntu) y SQL Server (Windows). El origen siempre forma parte de cada fila."
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => setReloadToken((value) => value + 1)}
              loading={loading}
              loadingLabel="Actualizando…"
              icon={<RefreshCw aria-hidden="true" size={17} />}
            >
              Actualizar
            </Button>
            <Button
              onClick={() => navigate("/records/new")}
              icon={<PlusCircle aria-hidden="true" size={17} />}
            >
              Nuevo registro
            </Button>
          </>
        }
      />

      <div className="stack-lg">
        <Card>
          <div className="card__body">
            <RecordsFilters
              applied={query}
              onApply={(next) => setQuery(next)}
              loading={loading}
            />
          </div>
        </Card>

        {data ? <SourceSummary data={data} /> : null}

        {failedSources.length > 0 ? (
          <Alert tone="warning" title="Resultados parciales" live>
            <p>
              No se pudieron consultar todos los servidores. Los resultados mostrados
              provienen únicamente de las fuentes disponibles.
            </p>
            <ul className="compact-list">
              {failedSources.map(([name, source]) => (
                <li key={name}>
                  <strong>{SERVER_LABEL[name as Servidor] ?? name}</strong>:{" "}
                  {SOURCE_STATUS_LABEL[source.status] ?? source.status}
                  {source.error === "database_unavailable"
                    ? " (base de datos no disponible)"
                    : ""}
                </li>
              ))}
            </ul>
          </Alert>
        ) : null}

        {error ? (
          <Alert
            tone="danger"
            title="No se pudo consultar el historial"
            live
            actions={
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setReloadToken((value) => value + 1)}
              >
                Reintentar
              </Button>
            }
          >
            {error}
          </Alert>
        ) : null}

        <Card className="records-card">
          <div className="card__header">
            <div>
              <h2>Observaciones</h2>
              <p className="muted small">
                {data
                  ? `${data.registros.length} registro(s) en esta página · desde el desplazamiento ${data.paginacion.offset}`
                  : "Consultando registros…"}
              </p>
            </div>
            <span className="records-card__icon" aria-hidden="true">
              <History size={20} />
            </span>
          </div>

          {loading && !data ? (
            <LoadingBlock label="Cargando registros de ambos servidores…" />
          ) : data && data.registros.length > 0 ? (
            <RecordTable
              records={data.registros}
              order={query.orden}
              direction={query.direccion}
              onSort={handleSort}
              onDetail={setSelected}
            />
          ) : data && !error ? (
            <EmptyState
              title={
                failedSources.length > 0
                  ? "No hay resultados en las fuentes disponibles"
                  : "No existen registros con estos filtros"
              }
              description={
                failedSources.length > 0
                  ? "Uno de los servidores no respondió. Prueba a actualizar o consulta el otro servidor por separado."
                  : "Guarda una observación o cambia los filtros para ampliar la búsqueda."
              }
              action={
                <Button
                  variant="secondary"
                  onClick={() => navigate("/records/new")}
                  icon={<PlusCircle aria-hidden="true" size={17} />}
                >
                  Crear registro
                </Button>
              }
            />
          ) : null}

          {data && data.registros.length > 0 ? (
            <div className="pagination">
              <p className="small muted">
                Página iniciada en {data.paginacion.offset} · límite {data.paginacion.limit} por
                servidor
              </p>
              <div className="cluster">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handlePage(-1)}
                  disabled={query.offset === 0 || loading}
                >
                  Anterior
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handlePage(1)}
                  disabled={!canNext || loading}
                >
                  Siguiente
                </Button>
              </div>
            </div>
          ) : null}
        </Card>

        {data?.paginacion.per_source ? (
          <p className="small muted">
            Consulta combinada: la API aplica el mismo límite y desplazamiento a cada
            servidor antes de combinar y ordenar los resultados. La paginación no
            representa un total global.
          </p>
        ) : null}
      </div>

      <RecordDetailDialog record={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function SourceSummary({ data }: { data: NonNullable<ReturnType<typeof useRecords>["data"]> }) {
  return (
    <Card className="source-summary" aria-label="Estado de las fuentes consultadas">
      <div className="source-summary__items">
        {Object.entries(data.fuentes).map(([name, source]) => {
          const servidor = name as Servidor;
          const Icon = servidor === "windows" ? Server : Database;
          const ok = source.status === "ok";
          return (
            <div className="source-summary__item" key={name}>
              <span
                className={["source-summary__icon", ok ? "" : "source-summary__icon--error"]
                  .filter(Boolean)
                  .join(" ")}
                aria-hidden="true"
              >
                <Icon size={18} />
              </span>
              <div>
                <p className="source-summary__name">
                  {SERVER_LABEL[servidor] ?? name}{" "}
                  <Badge tone={ok ? "success" : "warning"}>
                    {SOURCE_STATUS_LABEL[source.status] ?? source.status}
                  </Badge>
                </p>
                <p className="small muted">
                  {source.count} registro(s) en la página
                  {source.has_more ? " · hay más" : " · sin más páginas"}
                </p>
              </div>
            </div>
          );
        })}
        {data.parcial ? (
          <div className="source-summary__warning">
            <TriangleAlert aria-hidden="true" size={17} />
            Respuesta parcial
          </div>
        ) : null}
      </div>
    </Card>
  );
}
