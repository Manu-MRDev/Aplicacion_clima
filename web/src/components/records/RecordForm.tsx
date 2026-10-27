import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  ArrowLeft,
  CheckCircle2,
  DatabaseZap,
  MapPin,
  Save,
  ShieldAlert,
  ShieldCheck,
  UserRound,
} from "lucide-react";

import { useAuth } from "../../contexts/AuthContext";
import { createRecord } from "../../services/records";
import { ApiError } from "../../services/apiClient";
import type { Servidor } from "../../types/api";
import { SERVER_LABEL } from "../../types/api";
import type {
  CreateRecordResponse,
  RecordCreateInput,
  RecordPrefill,
} from "../../types/records";
import { formatDateTime, toDateTimeLocalValue } from "../../utils/dates";
import { errorMessage } from "../../utils/errors";
import {
  mapApiFieldErrors,
  validateRecordForm,
  type FieldErrors,
  type RecordFormValues,
} from "../../utils/validation";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { Field, fieldDescribedBy } from "../ui/Field";
import { PageHeader } from "../ui/PageHeader";
import { ServerSelector } from "./ServerSelector";
import { VoiceSaveControl } from "./VoiceSaveControl";

interface RecordLocationState {
  prefill?: RecordPrefill;
}

const EMPTY_VALUES: RecordFormValues = {
  servidor: "ubuntu",
  nombre: "",
  paterno: "",
  materno: "",
  estado: "",
  municipio: "",
  latitud: "",
  longitud: "",
  temperatura: "",
  humedad: "",
  viento: "",
  fechaHoraLocal: "",
};

function initialValues(prefill?: RecordPrefill): RecordFormValues {
  if (!prefill) return { ...EMPTY_VALUES };
  let fechaLocal = "";
  if (prefill.fecha_hora) {
    const parsed = new Date(prefill.fecha_hora);
    if (!Number.isNaN(parsed.getTime())) {
      fechaLocal = toDateTimeLocalValue(parsed);
    }
  }
  return {
    ...EMPTY_VALUES,
    nombre: "",
    estado: prefill.estado ?? "",
    municipio: prefill.municipio ?? "",
    latitud: String(prefill.latitud),
    longitud: String(prefill.longitud),
    temperatura: String(prefill.temperatura),
    humedad: String(prefill.humedad),
    viento: String(prefill.viento),
    fechaHoraLocal: fechaLocal,
  };
}

function toCreateInput(values: NonNullable<ReturnType<typeof validateRecordForm>["values"]>): RecordCreateInput {
  return {
    servidor: values.servidor,
    nombre: values.nombre,
    paterno: values.paterno,
    materno: values.materno,
    estado: values.estado,
    municipio: values.municipio,
    latitud: values.latitud,
    longitud: values.longitud,
    temperatura: values.temperatura,
    humedad: values.humedad,
    viento: values.viento,
    fecha_hora: values.fecha_hora,
  };
}

export function RecordForm() {
  const { user, csrfToken, refreshCsrf } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const prefill = (location.state as RecordLocationState | null)?.prefill;
  const [values, setValues] = useState<RecordFormValues>(() => initialValues(prefill));
  const [errors, setErrors] = useState<FieldErrors>({});
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingInput, setPendingInput] = useState<RecordCreateInput | null>(null);
  const [creating, setCreating] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<CreateRecordResponse | null>(null);
  const [resultWarning, setResultWarning] = useState<string | null>(null);
  const summaryRef = useRef<HTMLDivElement>(null);
  const inFlight = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (Object.keys(errors).length > 0) {
      window.requestAnimationFrame(() => summaryRef.current?.focus());
    }
  }, [errors]);

  const update = <K extends keyof RecordFormValues>(
    field: K,
    value: RecordFormValues[K],
  ) => {
    setValues((current) => ({ ...current, [field]: value }));
    if (errors[field]) {
      setErrors((current) => {
        const next = { ...current };
        delete next[field];
        return next;
      });
    }
  };

  const attemptSave = (servidorOverride?: Servidor | null): string => {
    if (result) {
      return "Este registro ya se guardó. Usa “Crear otro registro” para comenzar de nuevo.";
    }
    const selectedServer = servidorOverride ?? values.servidor;
    const candidate: RecordFormValues = { ...values, servidor: selectedServer };
    setValues(candidate);
    const validation = validateRecordForm(candidate);
    setErrors(validation.errors);
    setSubmitError(null);
    if (!validation.values) {
      window.requestAnimationFrame(() => summaryRef.current?.focus());
      return `No se puede guardar todavía en ${SERVER_LABEL[selectedServer]}: revisa los campos marcados.`;
    }
    setPendingInput(toCreateInput(validation.values));
    setConfirmOpen(true);
    return `Se preparó el guardado en ${SERVER_LABEL[selectedServer]}. Revisa el resumen y confirma el envío.`;
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    attemptSave(values.servidor);
  };

  const handleConfirm = async () => {
    if (!pendingInput || inFlight.current) return;
    if (!csrfToken) {
      setSubmitError(
        "No hay un token CSRF disponible. Vuelve a iniciar sesión para continuar.",
      );
      return;
    }
    inFlight.current = true;
    setCreating(true);
    setSubmitError(null);
    try {
      const response = await createRecord(pendingInput, csrfToken);
      if (!mounted.current) return;
      setResult(response);
      setConfirmOpen(false);
      setPendingInput(null);
      const integrity = response.integridad.status;
      if (integrity === "created") {
        setResultWarning(null);
      } else if (integrity === "disabled") {
        setResultWarning(
          "El registro se guardó, pero la integridad está deshabilitada en ese servidor.",
        );
      } else {
        setResultWarning(
          "El registro se guardó, pero no se pudo confirmar la protección de integridad.",
        );
      }
    } catch (error) {
      if (!mounted.current) return;
      setConfirmOpen(false);
      if (error instanceof ApiError) {
        if (error.status === 422) {
          const mapped = mapApiFieldErrors(error.details?.errors);
          if (Object.keys(mapped).length > 0) {
            setErrors(mapped);
          }
          setSubmitError(
            "El backend rechazó algunos datos. Revisa los campos marcados e intenta de nuevo.",
          );
        } else if (error.status === 403) {
          try {
            const refreshed = await refreshCsrf();
            setSubmitError(
              refreshed
                ? "La sesión se actualizó por seguridad. Revisa los datos y confirma de nuevo."
                : "La sesión ya no es válida. Vuelve a iniciar sesión.",
            );
          } catch {
            setSubmitError(
              "La sesión cambió y no se pudo actualizar. Vuelve a iniciar sesión.",
            );
          }
        } else if (error.status === 0) {
          setSubmitError(
            `${error.message} No se pudo confirmar si el registro se guardó; revisa el historial antes de reintentar.`,
          );
        } else if (pendingInput) {
          setSubmitError(
            `No se pudo guardar en ${SERVER_LABEL[pendingInput.servidor]}: ${error.message}`,
          );
        } else {
          setSubmitError(error.message);
        }
      } else {
        setSubmitError(
          errorMessage(error, "No se pudo guardar el registro. Intenta de nuevo."),
        );
      }
    } finally {
      inFlight.current = false;
      if (mounted.current) setCreating(false);
    }
  };

  const resetForAnother = () => {
    setResult(null);
    setResultWarning(null);
    setValues({ ...EMPTY_VALUES, servidor: values.servidor });
    setErrors({});
    setSubmitError(null);
    setPendingInput(null);
    setConfirmOpen(false);
  };

  if (result) {
    const record = result.registro;
    return (
      <div className="container page page-narrow">
        <PageHeader
          eyebrow="Registro guardado"
          title="La observación se guardó"
          description="La respuesta proviene del backend. La confirmación incluye el servidor y el estado de integridad real."
        />
        <Card className="record-success" as="section">
          <span className="record-success__icon" aria-hidden="true">
            <CheckCircle2 size={34} />
          </span>
          <div>
            <h2>Registro #{record.id}</h2>
            <p className="muted">
              Guardado en <strong>{SERVER_LABEL[record.servidor as Servidor]}</strong> el{" "}
              {formatDateTime(record.fecha_hora)}.
            </p>
          </div>
          <dl className="summary-grid">
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
              <dt>Ubicación</dt>
              <dd>
                {record.municipio}, {record.estado}
              </dd>
            </div>
            <div>
              <dt>Coordenadas</dt>
              <dd>
                {record.latitud ?? "—"}, {record.longitud ?? "—"}
              </dd>
            </div>
            <div>
              <dt>Temperatura</dt>
              <dd>{record.temperatura ?? "—"} °C</dd>
            </div>
            <div>
              <dt>Humedad / viento</dt>
              <dd>
                {record.humedad ?? "—"} % / {record.viento ?? "—"} km/h
              </dd>
            </div>
          </dl>
          {resultWarning ? (
            <Alert tone="warning" title="Integridad no confirmada" live>
              {resultWarning}
            </Alert>
          ) : (
            <Alert tone="success" title="Integridad confirmada" live>
              El bloque se creó en la cadena{" "}
              <span className="mono">{result.integridad.cadena}</span>
              {result.integridad.indice !== null
                ? ` con índice ${result.integridad.indice}`
                : ""}
              .
            </Alert>
          )}
          <div className="cluster">
            <Button onClick={() => navigate("/records")}>Ver historial</Button>
            <Button variant="secondary" onClick={resetForAnother}>
              Crear otro registro
            </Button>
            <Button variant="ghost" onClick={() => navigate("/")}>
              Volver al panel
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="container page">
      <PageHeader
        eyebrow="Nuevo registro climático"
        title="Guardar una observación"
        description="Revisa los datos, elige un único servidor y confirma la operación. El backend determina el usuario desde la sesión autenticada."
        actions={
          <Button
            variant="secondary"
            onClick={() => navigate(-1)}
            icon={<ArrowLeft aria-hidden="true" size={17} />}
          >
            Volver
          </Button>
        }
      />

      <form className="record-layout" onSubmit={handleSubmit} noValidate>
        <div className="record-main stack-lg">
          {prefill ? (
            <Alert tone="info" title="Datos precargados desde el panel">
              Se copiaron las coordenadas y las mediciones de la última consulta
              {prefill.locationLabel ? ` (${prefill.locationLabel})` : ""}. Revísalos y
              completa lo que falte antes de guardar.
            </Alert>
          ) : null}

          {submitError ? (
            <Alert tone="danger" title="No se guardó el registro" live>
              {submitError}
            </Alert>
          ) : null}

          {Object.keys(errors).length > 0 ? (
            <div
              className="form-error-summary"
              tabIndex={-1}
              ref={summaryRef}
              role="alert"
              aria-live="assertive"
            >
              <p>Revisa los siguientes campos:</p>
              <ul>
                {Object.entries(errors).map(([field, message]) => (
                  <li key={field}>
                    <a href={`#record-${field}`}>{message}</a>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <Card as="section">
            <div className="card__header">
              <div>
                <h2>Destino del registro</h2>
                <p className="muted small">Se guardará una sola vez en el servidor elegido.</p>
              </div>
              <DatabaseZap aria-hidden="true" className="section-icon" />
            </div>
            <div className="card__body">
              <ServerSelector
                value={values.servidor}
                onChange={(servidor) => update("servidor", servidor)}
                disabled={creating}
                error={errors.servidor}
              />
              <div className="identity-note">
                <span className="identity-note__icon" aria-hidden="true">
                  <ShieldCheck size={19} />
                </span>
                <div>
                  <p className="identity-note__title">Identidad de la sesión</p>
                  <p className="small muted">
                    El registro se asociará a <strong>{user?.username}</strong>. El campo
                    de usuario no se envía desde el formulario; lo deriva FastAPI.
                  </p>
                </div>
              </div>
            </div>
          </Card>

          <Card as="section">
            <div className="card__header">
              <div>
                <h2>Datos de la persona</h2>
                <p className="muted small">El nombre es obligatorio en ambos servidores.</p>
              </div>
              <UserRound aria-hidden="true" className="section-icon" />
            </div>
            <div className="card__body form-grid">
              <Field id="record-nombre" label="Nombre" required error={errors.nombre}>
                <input
                  id="record-nombre"
                  className="input"
                  maxLength={100}
                  value={values.nombre}
                  onChange={(event) => update("nombre", event.target.value)}
                  aria-invalid={errors.nombre ? true : undefined}
                  aria-describedby={fieldDescribedBy("record-nombre", errors.nombre)}
                  disabled={creating}
                  autoComplete="given-name"
                />
              </Field>
              <Field
                id="record-paterno"
                label="Apellido paterno"
                required={values.servidor === "windows"}
                error={errors.paterno}
                hint={
                  values.servidor === "windows"
                    ? "Obligatorio para SQL Server (Windows)."
                    : "Opcional en PostgreSQL."
                }
              >
                <input
                  id="record-paterno"
                  className="input"
                  maxLength={100}
                  value={values.paterno}
                  onChange={(event) => update("paterno", event.target.value)}
                  aria-invalid={errors.paterno ? true : undefined}
                  aria-describedby={fieldDescribedBy("record-paterno", errors.paterno, "hint")}
                  disabled={creating}
                  autoComplete="family-name"
                />
              </Field>
              <Field id="record-materno" label="Apellido materno" error={errors.materno}>
                <input
                  id="record-materno"
                  className="input"
                  maxLength={100}
                  value={values.materno}
                  onChange={(event) => update("materno", event.target.value)}
                  aria-invalid={errors.materno ? true : undefined}
                  aria-describedby={fieldDescribedBy("record-materno", errors.materno)}
                  disabled={creating}
                />
              </Field>
            </div>
          </Card>

          <Card as="section">
            <div className="card__header">
              <div>
                <h2>Ubicación</h2>
                <p className="muted small">Estado, municipio y coordenadas en grados decimales.</p>
              </div>
              <MapPin aria-hidden="true" className="section-icon" />
            </div>
            <div className="card__body form-grid form-grid--three">
              <Field id="record-estado" label="Estado" required error={errors.estado}>
                <input
                  id="record-estado"
                  className="input"
                  maxLength={120}
                  value={values.estado}
                  onChange={(event) => update("estado", event.target.value)}
                  aria-invalid={errors.estado ? true : undefined}
                  aria-describedby={fieldDescribedBy("record-estado", errors.estado)}
                  disabled={creating}
                />
              </Field>
              <Field id="record-municipio" label="Municipio" required error={errors.municipio}>
                <input
                  id="record-municipio"
                  className="input"
                  maxLength={120}
                  value={values.municipio}
                  onChange={(event) => update("municipio", event.target.value)}
                  aria-invalid={errors.municipio ? true : undefined}
                  aria-describedby={fieldDescribedBy("record-municipio", errors.municipio)}
                  disabled={creating}
                />
              </Field>
              <Field id="record-latitud" label="Latitud" required error={errors.latitud}>
                <input
                  id="record-latitud"
                  className="input"
                  type="number"
                  min={-90}
                  max={90}
                  step="any"
                  value={values.latitud}
                  onChange={(event) => update("latitud", event.target.value)}
                  aria-invalid={errors.latitud ? true : undefined}
                  aria-describedby={fieldDescribedBy("record-latitud", errors.latitud)}
                  disabled={creating}
                />
              </Field>
              <Field id="record-longitud" label="Longitud" required error={errors.longitud}>
                <input
                  id="record-longitud"
                  className="input"
                  type="number"
                  min={-180}
                  max={180}
                  step="any"
                  value={values.longitud}
                  onChange={(event) => update("longitud", event.target.value)}
                  aria-invalid={errors.longitud ? true : undefined}
                  aria-describedby={fieldDescribedBy("record-longitud", errors.longitud)}
                  disabled={creating}
                />
              </Field>
            </div>
          </Card>

          <Card as="section">
            <div className="card__header">
              <div>
                <h2>Mediciones</h2>
                <p className="muted small">
                  Rangos admitidos: temperatura -90 a 60 °C, humedad 0 a 100 %, viento 0 a
                  500 km/h.
                </p>
              </div>
            </div>
            <div className="card__body form-grid form-grid--three">
              <Field
                id="record-temperatura"
                label="Temperatura (°C)"
                required
                error={errors.temperatura}
              >
                <input
                  id="record-temperatura"
                  className="input"
                  type="number"
                  inputMode="decimal"
                  min={-90}
                  max={60}
                  step="0.01"
                  value={values.temperatura}
                  onChange={(event) => update("temperatura", event.target.value)}
                  aria-invalid={errors.temperatura ? true : undefined}
                  aria-describedby={fieldDescribedBy("record-temperatura", errors.temperatura)}
                  disabled={creating}
                />
              </Field>
              <Field id="record-humedad" label="Humedad relativa (%)" required error={errors.humedad}>
                <input
                  id="record-humedad"
                  className="input"
                  type="number"
                  inputMode="decimal"
                  min={0}
                  max={100}
                  step="0.01"
                  value={values.humedad}
                  onChange={(event) => update("humedad", event.target.value)}
                  aria-invalid={errors.humedad ? true : undefined}
                  aria-describedby={fieldDescribedBy("record-humedad", errors.humedad)}
                  disabled={creating}
                />
              </Field>
              <Field id="record-viento" label="Viento (km/h)" required error={errors.viento}>
                <input
                  id="record-viento"
                  className="input"
                  type="number"
                  inputMode="decimal"
                  min={0}
                  max={500}
                  step="0.01"
                  value={values.viento}
                  onChange={(event) => update("viento", event.target.value)}
                  aria-invalid={errors.viento ? true : undefined}
                  aria-describedby={fieldDescribedBy("record-viento", errors.viento)}
                  disabled={creating}
                />
              </Field>
            </div>
          </Card>

          <Card as="section">
            <div className="card__header">
              <div>
                <h2>Fecha de observación</h2>
                <p className="muted small">
                  Opcional. Si se omite, el backend usará la hora UTC actual.
                </p>
              </div>
            </div>
            <div className="card__body">
              <Field
                id="record-fechaHoraLocal"
                label="Fecha y hora local"
                error={errors.fechaHoraLocal}
                hint="Se convertirá a UTC antes de enviarla. No puede estar en el futuro."
              >
                <input
                  id="record-fechaHoraLocal"
                  className="input"
                  type="datetime-local"
                  max={toDateTimeLocalValue(new Date())}
                  value={values.fechaHoraLocal}
                  onChange={(event) => update("fechaHoraLocal", event.target.value)}
                  aria-invalid={errors.fechaHoraLocal ? true : undefined}
                  aria-describedby={fieldDescribedBy(
                    "record-fechaHoraLocal",
                    errors.fechaHoraLocal,
                    "hint",
                  )}
                  disabled={creating}
                />
              </Field>
            </div>
          </Card>

          <div className="record-submit">
            <div>
              <p className="record-submit__destination">
                Destino seleccionado: <strong>{SERVER_LABEL[values.servidor]}</strong>
              </p>
              <p className="small muted">
                Se solicitará una confirmación antes de enviar. El formulario no permite
                envíos dobles.
              </p>
            </div>
            <Button
              type="submit"
              size="lg"
              loading={creating}
              loadingLabel="Guardando…"
              icon={<Save aria-hidden="true" size={19} />}
            >
              Revisar y guardar
            </Button>
          </div>
        </div>

        <aside className="record-aside stack-lg" aria-label="Ayuda y voz">
          <Card>
            <div className="card__body">
              <VoiceSaveControl
                disabled={creating}
                onSaveRequested={(servidor) => attemptSave(servidor)}
              />
            </div>
          </Card>
          <Card tone="soft">
            <div className="card__body">
              <h2>Antes de guardar</h2>
              <ul className="check-list">
                <li>
                  <ShieldCheck aria-hidden="true" size={16} /> El usuario se deriva de la
                  sesión.
                </li>
                <li>
                  <DatabaseZap aria-hidden="true" size={16} /> Se elige un solo servidor.
                </li>
                <li>
                  <ShieldAlert aria-hidden="true" size={16} /> La integridad se confirma
                  solo con la respuesta del backend.
                </li>
              </ul>
            </div>
          </Card>
        </aside>
      </form>

      <ConfirmDialog
        open={confirmOpen}
        title="Confirmar guardado"
        description="Revisa el destino y los datos principales antes de enviar el registro."
        confirmLabel="Guardar registro"
        loading={creating}
        onCancel={() => {
          if (!creating) {
            setConfirmOpen(false);
            setPendingInput(null);
          }
        }}
        onConfirm={() => void handleConfirm()}
      >
        {pendingInput ? (
          <dl className="summary-grid">
            <div>
              <dt>Servidor</dt>
              <dd>{SERVER_LABEL[pendingInput.servidor]}</dd>
            </div>
            <div>
              <dt>Usuario de sesión</dt>
              <dd>{user?.username}</dd>
            </div>
            <div>
              <dt>Nombre</dt>
              <dd>
                {[pendingInput.nombre, pendingInput.paterno, pendingInput.materno]
                  .filter(Boolean)
                  .join(" ")}
              </dd>
            </div>
            <div>
              <dt>Ubicación</dt>
              <dd>
                {pendingInput.municipio}, {pendingInput.estado}
              </dd>
            </div>
            <div>
              <dt>Mediciones</dt>
              <dd>
                {pendingInput.temperatura} °C · {pendingInput.humedad} % ·{" "}
                {pendingInput.viento} km/h
              </dd>
            </div>
            <div>
              <dt>Fecha</dt>
              <dd>{pendingInput.fecha_hora ? formatDateTime(pendingInput.fecha_hora) : "Ahora (UTC)"}</dd>
            </div>
          </dl>
        ) : null}
      </ConfirmDialog>
    </div>
  );
}
