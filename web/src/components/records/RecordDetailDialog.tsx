import { useEffect, useState } from "react";

import { Database, Server } from "lucide-react";

import { getRecord } from "../../services/records";
import type { Servidor } from "../../types/api";
import { SERVER_LABEL } from "../../types/api";
import type { WeatherRecord } from "../../types/records";
import { formatDateTime, formatNumber } from "../../utils/dates";
import { errorMessage } from "../../utils/errors";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Modal } from "../ui/Modal";
import { LoadingBlock } from "../ui/Spinner";

interface RecordDetailDialogProps {
  record: WeatherRecord | null;
  onClose: () => void;
}

export function RecordDetailDialog({ record, onClose }: RecordDetailDialogProps) {
  const [detail, setDetail] = useState<WeatherRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!record) {
      setDetail(null);
      setError(null);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setDetail(null);
    getRecord(record.id, record.servidor as Servidor, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) setDetail(response);
      })
      .catch((loadError) => {
        if (!controller.signal.aborted) {
          setError(
            errorMessage(loadError, "No se pudo obtener el detalle del registro."),
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [record]);

  return (
    <Modal
      open={record !== null}
      title={record ? `Registro #${record.id}` : "Detalle del registro"}
      description={
        record
          ? `Consulta directa a ${SERVER_LABEL[record.servidor as Servidor] ?? record.servidor}.`
          : undefined
      }
      onClose={onClose}
      size="lg"
    >
      {loading ? <LoadingBlock label="Cargando detalle…" /> : null}
      {error ? (
        <Alert tone="danger" title="No se pudo cargar el detalle">
          {error}
        </Alert>
      ) : null}
      {detail ? <RecordDetail record={detail} /> : null}
    </Modal>
  );
}

function RecordDetail({ record }: { record: WeatherRecord }) {
  const servidor = record.servidor as Servidor;
  const Icon = servidor === "windows" ? Server : Database;
  return (
    <div className="stack">
      <Badge
        tone={servidor === "windows" ? "info" : "success"}
        icon={<Icon aria-hidden="true" size={14} />}
      >
        {SERVER_LABEL[servidor] ?? record.servidor}
      </Badge>
      <dl className="summary-grid summary-grid--detail">
        <div>
          <dt>Usuario</dt>
          <dd>{record.usuario}</dd>
        </div>
        <div>
          <dt>Nombre completo</dt>
          <dd>
            {[record.nombre, record.paterno, record.materno].filter(Boolean).join(" ")}
          </dd>
        </div>
        <div>
          <dt>Estado</dt>
          <dd>{record.estado}</dd>
        </div>
        <div>
          <dt>Municipio</dt>
          <dd>{record.municipio}</dd>
        </div>
        <div>
          <dt>Latitud</dt>
          <dd className="mono">{formatNumber(record.latitud, 7)}</dd>
        </div>
        <div>
          <dt>Longitud</dt>
          <dd className="mono">{formatNumber(record.longitud, 7)}</dd>
        </div>
        <div>
          <dt>Temperatura</dt>
          <dd>{formatNumber(record.temperatura, 2)} °C</dd>
        </div>
        <div>
          <dt>Humedad relativa</dt>
          <dd>{formatNumber(record.humedad, 2)} %</dd>
        </div>
        <div>
          <dt>Viento</dt>
          <dd>{formatNumber(record.viento, 2)} km/h</dd>
        </div>
        <div>
          <dt>Fecha y hora</dt>
          <dd>{formatDateTime(record.fecha_hora)}</dd>
        </div>
      </dl>
      <p className="small muted">
        El identificador solo es único dentro de su servidor. Por eso el detalle siempre
        incluye el origen.
      </p>
    </div>
  );
}
