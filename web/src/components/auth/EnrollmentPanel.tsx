import { useRef, useState, type FormEvent } from "react";

import {
  ArrowLeft,
  Check,
  Copy,
  KeyRound,
  QrCode,
  ShieldCheck,
  Smartphone,
} from "lucide-react";

import { useAuth } from "../../contexts/AuthContext";
import type { EnrollmentResponse } from "../../types/auth";
import { errorMessage } from "../../utils/errors";
import { isValidTotpFormat } from "../../utils/validation";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Field } from "../ui/Field";

export function EnrollmentPanel() {
  const { pending, enrollTotp, confirmTotp, cancelPending } = useAuth();
  const [enrollment, setEnrollment] = useState<EnrollmentResponse | null>(null);
  const [starting, setStarting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const inFlight = useRef(false);

  if (!pending) return null;

  const startEnrollment = async () => {
    if (starting) return;
    setStarting(true);
    setError(null);
    try {
      const response = await enrollTotp();
      setEnrollment(response);
    } catch (enrollError) {
      setError(
        errorMessage(
          enrollError,
          "No se pudo generar la inscripción TOTP. Intenta de nuevo.",
        ),
      );
    } finally {
      setStarting(false);
    }
  };

  const handleConfirm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (inFlight.current || !enrollment) return;
    if (!isValidTotpFormat(code)) {
      setError("Introduce los seis dígitos que muestra la aplicación autenticadora.");
      return;
    }
    inFlight.current = true;
    setConfirming(true);
    setError(null);
    try {
      await confirmTotp(code);
    } catch (confirmError) {
      setError(
        errorMessage(
          confirmError,
          "No se pudo confirmar el código. Verifica la hora del dispositivo e intenta de nuevo.",
        ),
      );
      setCode("");
    } finally {
      inFlight.current = false;
      setConfirming(false);
    }
  };

  const copyKey = async () => {
    if (!enrollment) return;
    try {
      await navigator.clipboard.writeText(enrollment.manual_key);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setError(
        "No se pudo copiar automáticamente. Selecciona la clave manual y cópiala.",
      );
    }
  };

  const handleCancel = async () => {
    setCancelling(true);
    setEnrollment(null);
    setCode("");
    try {
      await cancelPending();
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className="auth-card auth-card--wide">
      <div className="auth-card__icon" aria-hidden="true">
        <Smartphone size={26} />
      </div>
      <div className="auth-card__heading">
        <p className="auth-card__eyebrow">Configuración inicial</p>
        <h1>Configura tu autenticador</h1>
        <p className="muted">
          La cuenta <strong>{pending.username}</strong> todavía no tiene segundo factor.
          Debes configurarlo antes de acceder al panel.
        </p>
      </div>

      {error ? (
        <Alert tone="danger" title="No se pudo completar la inscripción" live>
          {error}
        </Alert>
      ) : null}

      {!enrollment ? (
        <div className="stack">
          <div className="instruction-list">
            <div>
              <span className="instruction-list__step">1</span>
              <p>
                Abre <strong>Google Authenticator</strong> o{" "}
                <strong>Microsoft Authenticator</strong> en tu teléfono.
              </p>
            </div>
            <div>
              <span className="instruction-list__step">2</span>
              <p>Pulsa “Generar código QR” y escanea la imagen que devuelve la API.</p>
            </div>
            <div>
              <span className="instruction-list__step">3</span>
              <p>Introduce el código de seis dígitos para confirmar y entrar.</p>
            </div>
          </div>

          <Alert tone="warning" title="La clave se muestra una sola vez">
            No compartas el QR ni la clave manual. Esta pantalla solo está disponible
            después de validar tu contraseña.
          </Alert>

          <Button
            size="lg"
            fullWidth
            onClick={() => void startEnrollment()}
            loading={starting}
            loadingLabel="Generando inscripción…"
            icon={<QrCode aria-hidden="true" size={19} />}
          >
            Generar código QR
          </Button>
        </div>
      ) : (
        <div className="stack-lg">
          <div className="enrollment-grid">
            <div className="qr-panel">
              <img
                src={enrollment.qr_data_uri}
                alt={`Código QR de inscripción para ${enrollment.account}`}
                width={220}
                height={220}
              />
              <p className="small muted">
                Emisor: {enrollment.issuer} · Cuenta: {enrollment.account}
              </p>
            </div>
            <div className="stack">
              <div>
                <p className="field__label">Clave manual</p>
                <code className="manual-key" aria-label="Clave manual TOTP">
                  {enrollment.manual_key}
                </code>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void copyKey()}
                icon={
                  copied ? (
                    <Check aria-hidden="true" size={17} />
                  ) : (
                    <Copy aria-hidden="true" size={17} />
                  )
                }
              >
                {copied ? "Clave copiada" : "Copiar clave manual"}
              </Button>
              <p className="small muted">
                Si no puedes escanear el QR, introduce esta clave manualmente en tu
                aplicación autenticadora.
              </p>
            </div>
          </div>

          <form
            className="auth-form"
            onSubmit={(event) => void handleConfirm(event)}
            noValidate
          >
            <Field
              id="enroll-code"
              label="Código generado por la aplicación"
              required
              hint="Seis dígitos. La validación definitiva la realiza FastAPI."
            >
              <div className="input-with-icon">
                <KeyRound aria-hidden="true" size={18} />
                <input
                  id="enroll-code"
                  className="input totp-input"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  value={code}
                  onChange={(event) =>
                    setCode(event.target.value.replace(/\D/g, "").slice(0, 6))
                  }
                  disabled={confirming}
                  autoFocus
                  required
                />
              </div>
            </Field>

            <Button
              type="submit"
              size="lg"
              fullWidth
              loading={confirming}
              loadingLabel="Confirmando inscripción…"
              disabled={!isValidTotpFormat(code)}
              icon={<ShieldCheck aria-hidden="true" size={19} />}
            >
              Confirmar y entrar
            </Button>
          </form>
        </div>
      )}

      <Button
        variant="ghost"
        onClick={() => void handleCancel()}
        loading={cancelling}
        loadingLabel="Volviendo…"
        icon={<ArrowLeft aria-hidden="true" size={17} />}
      >
        Cancelar y volver al inicio de sesión
      </Button>

      <p className="auth-card__footnote small muted">
        El secreto TOTP se genera y cifra en el backend. Este navegador no lo guarda.
      </p>
    </div>
  );
}
