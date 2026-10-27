import { useEffect, useState, type FormEvent } from "react";

import { Filter, RotateCcw, SlidersHorizontal } from "lucide-react";

import type { Direccion, OrdenCampo, ServidorQuery } from "../../types/api";
import type { RecordsQuery } from "../../types/records";
import { Button } from "../ui/Button";
import { Field } from "../ui/Field";

interface RecordsFiltersProps {
  applied: RecordsQuery;
  onApply: (query: RecordsQuery) => void;
  loading: boolean;
}

interface Draft {
  servidor: ServidorQuery;
  usuario: string;
  desde: string;
  hasta: string;
  limit: number;
  orden: OrdenCampo;
  direccion: Direccion;
}

function draftFromQuery(query: RecordsQuery): Draft {
  return {
    servidor: query.servidor,
    usuario: query.usuario ?? "",
    desde: "",
    hasta: "",
    limit: query.limit,
    orden: query.orden,
    direccion: query.direccion,
  };
}

export function RecordsFilters({ applied, onApply, loading }: RecordsFiltersProps) {
  const [draft, setDraft] = useState<Draft>(() => draftFromQuery(applied));
  const [errors, setErrors] = useState<{ usuario?: string; range?: string }>({});

  // La tabla también puede cambiar el orden; reflejarlo sin descartar los
  // filtros que el usuario todavía no haya aplicado.
  useEffect(() => {
    setDraft((current) => ({
      ...current,
      limit: applied.limit,
      orden: applied.orden,
      direccion: applied.direccion,
    }));
  }, [applied.limit, applied.orden, applied.direccion]);

  const update = <K extends keyof Draft>(field: K, value: Draft[K]) => {
    setDraft((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: { usuario?: string; range?: string } = {};
    const usuario = draft.usuario.trim();
    if (usuario.length > 64) {
      nextErrors.usuario = "El usuario no puede superar 64 caracteres.";
    }
    if (draft.desde && draft.hasta && new Date(draft.desde) > new Date(draft.hasta)) {
      nextErrors.range = "La fecha inicial no puede ser posterior a la final.";
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    onApply({
      servidor: draft.servidor,
      usuario: usuario || undefined,
      desde: draft.desde ? new Date(draft.desde).toISOString() : undefined,
      hasta: draft.hasta ? new Date(draft.hasta).toISOString() : undefined,
      limit: draft.limit,
      offset: 0,
      orden: draft.orden,
      direccion: draft.direccion,
    });
  };

  const reset = () => {
    const next: Draft = {
      servidor: "ambos",
      usuario: "",
      desde: "",
      hasta: "",
      limit: 25,
      orden: "fecha_hora",
      direccion: "desc",
    };
    setDraft(next);
    setErrors({});
    onApply({
      servidor: next.servidor,
      limit: next.limit,
      offset: 0,
      orden: next.orden,
      direccion: next.direccion,
    });
  };

  return (
    <form className="records-filters" onSubmit={handleSubmit} noValidate>
      <div className="records-filters__title">
        <Filter aria-hidden="true" size={18} />
        <h2>Filtros</h2>
        <span className="small muted">Los filtros se aplican al pulsar el botón.</span>
      </div>

      <div className="records-filters__grid">
        <Field id="filter-servidor" label="Servidor">
          <select
            id="filter-servidor"
            className="select"
            value={draft.servidor}
            onChange={(event) => update("servidor", event.target.value as ServidorQuery)}
            disabled={loading}
          >
            <option value="ambos">Ambos servidores</option>
            <option value="ubuntu">PostgreSQL · Ubuntu</option>
            <option value="windows">SQL Server · Windows</option>
          </select>
        </Field>

        <Field
          id="filter-usuario"
          label="Usuario exacto"
          error={errors.usuario}
          hint="Sin filtro si se deja vacío."
        >
          <input
            id="filter-usuario"
            className="input"
            value={draft.usuario}
            onChange={(event) => update("usuario", event.target.value)}
            maxLength={64}
            disabled={loading}
            autoComplete="off"
          />
        </Field>

        <Field id="filter-desde" label="Desde" error={errors.range}>
          <input
            id="filter-desde"
            className="input"
            type="datetime-local"
            value={draft.desde}
            onChange={(event) => update("desde", event.target.value)}
            disabled={loading}
          />
        </Field>

        <Field id="filter-hasta" label="Hasta">
          <input
            id="filter-hasta"
            className="input"
            type="datetime-local"
            value={draft.hasta}
            onChange={(event) => update("hasta", event.target.value)}
            disabled={loading}
          />
        </Field>

        <Field id="filter-limit" label="Registros por página">
          <select
            id="filter-limit"
            className="select"
            value={draft.limit}
            onChange={(event) => update("limit", Number(event.target.value))}
            disabled={loading}
          >
            {[25, 50, 100, 200].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </Field>

        <Field id="filter-orden" label="Ordenar por">
          <select
            id="filter-orden"
            className="select"
            value={draft.orden}
            onChange={(event) => update("orden", event.target.value as OrdenCampo)}
            disabled={loading}
          >
            <option value="fecha_hora">Fecha y hora</option>
            <option value="id">ID</option>
          </select>
        </Field>

        <Field id="filter-direccion" label="Dirección">
          <select
            id="filter-direccion"
            className="select"
            value={draft.direccion}
            onChange={(event) => update("direccion", event.target.value as Direccion)}
            disabled={loading}
          >
            <option value="desc">Descendente</option>
            <option value="asc">Ascendente</option>
          </select>
        </Field>
      </div>

      <div className="records-filters__actions">
        <Button
          type="submit"
          loading={loading}
          loadingLabel="Consultando…"
          icon={<SlidersHorizontal aria-hidden="true" size={17} />}
        >
          Aplicar filtros
        </Button>
        <Button
          variant="ghost"
          onClick={reset}
          disabled={loading}
          icon={<RotateCcw aria-hidden="true" size={16} />}
        >
          Restablecer
        </Button>
      </div>
      <p className="small muted records-filters__note">
        Al consultar ambos servidores, el límite y el desplazamiento se aplican por
        separado en cada fuente, tal como define la API. Los IDs pueden repetirse entre
        servidores.
      </p>
    </form>
  );
}
