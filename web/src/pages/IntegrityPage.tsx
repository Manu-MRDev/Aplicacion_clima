import { useRef, useState } from "react";

import {
  Database,
  DatabaseZap,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  Server,
  TriangleAlert,
} from "lucide-react";

import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { LoadingBlock } from "../components/ui/Spinner";
import { verifyIntegrity } from "../services/integrity";
import type { ServidorQuery } from "../types/api";
import { SERVER_LABEL } from "../types/api";
import type { IntegritySourceReport, IntegrityVerifyResponse } from "../types/integrity";
import { formatDateTime } from "../utils/dates";
import {
  errorMessage,
  INTEGRITY_STATUS_LABEL,
  integrityTone,
} from "../utils/errors";

const SERVER_OPTIONS: Array<{ value: ServidorQuery; label: string; description: string }> = [
  { value: "ambos", label: "Ambos servidores", description: "PostgreSQL y SQL Server" },
  { value: "ubuntu", label: "PostgreSQL · Ubuntu", description: "Cadena api-ubuntu" },
  { value: "windows", label: "SQL Server · Windows", description: "Cadena api-windows" },
];

export function IntegrityPage() {
  const [servidor, setServidor] = useState<ServidorQuery>("ambos");
  const [result, setResult] = useState<IntegrityVerifyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<string | null>(null);
  const inFlight = useRef(false);

  const runVerification = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await verifyIntegrity(servidor);
      setResult(response);
      setLastRun(new Date().toISOString());
    } catch (verificationError) {
      setError(
        errorMessage(
          verificationError,
          "No se pudo ejecutar la verificación de integridad.",
        ),
      );
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  };

  const globalTone = result ? integrityTone(result.status) : "neutral";

  return (
    <div className="container page">
      <PageHeader
        eyebrow="Seguridad de los datos"
        title="Verificación de integridad"
        description="La comprobación la realiza FastAPI sobre las cadenas de hashes. El frontend no calcula ni valida hashes."
      />

      <div className="integrity-layout">
        <Card as="section" className="integrity-control">
          <div className="card__body stack">
            <fieldset className="server-query" aria-describedby="integrity-server-hint">
              <legend className="field__label">Servidor a verificar</legend>
              <p id="integrity-server-hint" className="field__hint">
                Puedes comprobar una cadena o ambos servidores.
              </p>
              <div className="server-query__options">
                {SERVER_OPTIONS.map((option) => (
                  <label
                    key={option.value}
                    className={[
                      "server-query__option",
                      servidor === option.value ? "server-query__option--selected" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <input
                      type="radio"
                      name="integrity-servidor"
                      value={option.value}
                      checked={servidor === option.value}
                      onChange={() => setServidor(option.value)}
                      className="visually-hidden"
                      disabled={loading}
                    />
                    <strong>{option.label}</strong>
                    <span className="small muted">{option.description}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <Button
              size="lg"
              fullWidth
              onClick={() => void runVerification()}
              loading={loading}
              loadingLabel="Verificando cadenas…"
              icon={<ShieldCheck aria-hidden="true" size={19} />}
            >
              Ejecutar verificación
            </Button>

            <div className="integrity-control__notes">
              <p className="small muted">
                La verificación es una lectura: no modifica registros ni bloques. Si uno
                de los servidores no está disponible, el resultado se marcará como
                parcial o no disponible.
              </p>
              {lastRun ? (
                <p className="small muted">
                  Última ejecución: <time dateTime={lastRun}>{formatDateTime(lastRun)}</time>
                </p>
              ) : null}
            </div>
          </div>
        </Card>

        <div className="integrity-results stack-lg" aria-live="polite">
          {error ? (
            <Alert
              tone="danger"
              title="No se pudo verificar"
              actions={
                <Button variant="secondary" size="sm" onClick={() => void runVerification()}>
                  Reintentar
                </Button>
              }
            >
              {error}
            </Alert>
          ) : null}

          {loading ? <LoadingBlock label="Verificando bloques y registros…" /> : null}

          {!loading && !result && !error ? (
            <Card>
              <EmptyState
                icon={<ShieldQuestion size={28} />}
                title="Aún no se ha ejecutado la verificación"
                description="Elige el servidor y pulsa “Ejecutar verificación”. No se mostrará un estado correcto hasta recibir la respuesta de FastAPI."
              />
            </Card>
          ) : null}

          {result ? (
            <>
              <Card className={`integrity-summary integrity-summary--${globalTone}`}>
                <div className="integrity-summary__main">
                  <span className="integrity-summary__icon" aria-hidden="true">
                    {result.status === "ok" ? (
                      <ShieldCheck size={34} />
                    ) : result.status === "invalid" ? (
                      <ShieldAlert size={34} />
                    ) : result.status === "empty" ? (
                      <ShieldQuestion size={34} />
                    ) : (
                      <TriangleAlert size={34} />
                    )}
                  </span>
                  <div>
                    <p className="integrity-summary__eyebrow">Resultado global</p>
                    <h2>{INTEGRITY_STATUS_LABEL[result.status] ?? result.status}</h2>
                    <p className="small muted">
                      Servidor solicitado:{" "}
                      {result.servidor === "ambos"
                        ? "ambos"
                        : SERVER_LABEL[result.servidor as "ubuntu" | "windows"] ??
                          result.servidor}
                      {lastRun ? ` · ${formatDateTime(lastRun)}` : ""}
                    </p>
                  </div>
                </div>
                {result.status === "empty" ? (
                  <p className="small">
                    Todavía no hay bloques nuevos en las cadenas verificadas. No es un
                    fallo: la cadena se crea con el primer registro guardado por esta API.
                  </p>
                ) : null}
                {result.status === "partial" ? (
                  <p className="small">
                    No todas las fuentes pudieron verificarse. Revisa el estado de cada
                    servidor antes de concluir.
                  </p>
                ) : null}
              </Card>

              <div className="integrity-sources">
                {Object.entries(result.sources).map(([name, report]) => (
                  <SourceReport key={name} name={name} report={report} />
                ))}
              </div>

              <Alert tone="neutral" title="Cómo interpretar el resultado">
                <p>
                  Los registros sin bloque se informan como advertencia porque la tabla es
                  compartida con datos históricos; no invalidan la cadena. Una ruptura de
                  secuencia, un hash incorrecto o un registro alterado sí la invalidan.
                </p>
                <p className="small">
                  Las cadenas heredadas <span className="mono">ubuntu</span> y{" "}
                  <span className="mono">windows</span> no se verifican con este formato.
                </p>
              </Alert>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function SourceReport({ name, report }: { name: string; report: IntegritySourceReport }) {
  const tone = integrityTone(report.status);
  const servidor = name as "ubuntu" | "windows";
  const Icon = servidor === "windows" ? Server : Database;
  return (
    <Card className={`source-report source-report--${tone}`} as="article">
      <div className="source-report__header">
        <div className="source-report__title">
          <span className="source-report__icon" aria-hidden="true">
            <Icon size={19} />
          </span>
          <div>
            <h3>{SERVER_LABEL[servidor] ?? name}</h3>
            <p className="small muted">{report.servidor}</p>
          </div>
        </div>
        <Badge tone={toneToBadge(tone)}>
          {INTEGRITY_STATUS_LABEL[report.status] ?? report.status}
        </Badge>
      </div>

      <dl className="integrity-stats">
        <div>
          <dt>Bloques verificados</dt>
          <dd>{report.bloques_verificados}</dd>
        </div>
        <div>
          <dt>Registros verificados</dt>
          <dd>{report.registros_verificados}</dd>
        </div>
        <div>
          <dt>Registros sin bloque</dt>
          <dd>{report.registros_sin_bloque}</dd>
        </div>
      </dl>

      {report.errores.length > 0 ? (
        <div className="source-report__section source-report__section--error">
          <p className="source-report__section-title">
            <ShieldAlert aria-hidden="true" size={16} /> Errores detectados
          </p>
          <ul className="compact-list">
            {report.errores.map((item, index) => (
              <li key={`${item}-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {report.advertencias.length > 0 ? (
        <div className="source-report__section source-report__section--warning">
          <p className="source-report__section-title">
            <TriangleAlert aria-hidden="true" size={16} /> Advertencias
          </p>
          <ul className="compact-list">
            {report.advertencias.map((item, index) => (
              <li key={`${item}-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {report.status === "ok" &&
      report.errores.length === 0 &&
      report.advertencias.length === 0 ? (
        <p className="source-report__ok small">
          <DatabaseZap aria-hidden="true" size={15} /> Sin errores ni advertencias en esta
          fuente.
        </p>
      ) : null}
    </Card>
  );
}

function toneToBadge(tone: ReturnType<typeof integrityTone>) {
  if (tone === "success") return "success" as const;
  if (tone === "warning") return "warning" as const;
  if (tone === "danger") return "danger" as const;
  if (tone === "info") return "info" as const;
  return "neutral" as const;
}
