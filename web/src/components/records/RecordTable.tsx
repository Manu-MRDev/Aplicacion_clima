import { ArrowDown, ArrowUp, ChevronRight, Database, Server } from "lucide-react";

import type { Direccion, OrdenCampo, Servidor } from "../../types/api";
import { SERVER_LABEL } from "../../types/api";
import type { WeatherRecord } from "../../types/records";
import { formatDateTime, formatNumber } from "../../utils/dates";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";

interface RecordTableProps {
  records: WeatherRecord[];
  order: OrdenCampo;
  direction: Direccion;
  onSort: (field: OrdenCampo) => void;
  onDetail: (record: WeatherRecord) => void;
}

function fullName(record: WeatherRecord): string {
  return [record.nombre, record.paterno, record.materno].filter(Boolean).join(" ") || "—";
}

export function RecordTable({
  records,
  order,
  direction,
  onSort,
  onDetail,
}: RecordTableProps) {
  return (
    <div
      className="table-scroll"
      tabIndex={0}
      role="region"
      aria-label="Tabla de registros climáticos; desplázate horizontalmente si es necesario"
    >
      <table className="data-table">
        <caption className="visually-hidden">
          Registros climáticos guardados en PostgreSQL y SQL Server
        </caption>
        <thead>
          <tr>
            <th scope="col">Origen</th>
            <th scope="col" aria-sort={sortValue(order, direction, "id")}>
              <SortButton
                field="id"
                label="ID"
                currentOrder={order}
                direction={direction}
                onSort={onSort}
              />
            </th>
            <th scope="col">Usuario</th>
            <th scope="col">Nombre completo</th>
            <th scope="col">Ubicación</th>
            <th scope="col">Coordenadas</th>
            <th scope="col">Temp.</th>
            <th scope="col">Humedad</th>
            <th scope="col">Viento</th>
            <th scope="col" aria-sort={sortValue(order, direction, "fecha_hora")}>
              <SortButton
                field="fecha_hora"
                label="Fecha y hora"
                currentOrder={order}
                direction={direction}
                onSort={onSort}
              />
            </th>
            <th scope="col">
              <span className="visually-hidden">Detalle</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {records.map((record) => {
            const servidor = record.servidor as Servidor;
            const Icon = servidor === "windows" ? Server : Database;
            return (
              <tr key={`${record.servidor}-${record.id}`}>
                <td>
                  <Badge
                    tone={servidor === "windows" ? "info" : "success"}
                    icon={<Icon aria-hidden="true" size={13} />}
                  >
                    {SERVER_LABEL[servidor] ?? record.servidor}
                  </Badge>
                </td>
                <td className="mono">{record.id}</td>
                <td>{record.usuario}</td>
                <td>{fullName(record)}</td>
                <td>
                  <span className="table-primary">{record.municipio}</span>
                  <span className="table-secondary">{record.estado}</span>
                </td>
                <td className="mono table-nowrap">
                  {formatNumber(record.latitud, 5)}, {formatNumber(record.longitud, 5)}
                </td>
                <td>{formatNumber(record.temperatura, 1)} °C</td>
                <td>{formatNumber(record.humedad, 1)} %</td>
                <td>{formatNumber(record.viento, 1)} km/h</td>
                <td className="table-nowrap">{formatDateTime(record.fecha_hora)}</td>
                <td>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onDetail(record)}
                    aria-label={`Ver detalle del registro ${record.id} de ${SERVER_LABEL[servidor] ?? record.servidor}`}
                    iconAfter={<ChevronRight aria-hidden="true" size={16} />}
                  >
                    Ver
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function sortValue(
  order: OrdenCampo,
  direction: Direccion,
  field: OrdenCampo,
): "ascending" | "descending" | "none" {
  if (order !== field) return "none";
  return direction === "asc" ? "ascending" : "descending";
}

function SortButton({
  field,
  label,
  currentOrder,
  direction,
  onSort,
}: {
  field: OrdenCampo;
  label: string;
  currentOrder: OrdenCampo;
  direction: Direccion;
  onSort: (field: OrdenCampo) => void;
}) {
  const active = currentOrder === field;
  const Icon = direction === "asc" ? ArrowUp : ArrowDown;
  return (
    <button
      type="button"
      className={["sort-button", active ? "sort-button--active" : ""]
        .filter(Boolean)
        .join(" ")}
      onClick={() => onSort(field)}
    >
      {label}
      {active ? <Icon aria-hidden="true" size={13} /> : null}
    </button>
  );
}
