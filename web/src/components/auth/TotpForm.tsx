import { useRef, useState, type FormEvent } from "react";

import { ArrowLeft, KeyRound, ShieldCheck } from "lucide-react";

import { useAuth } from "../../contexts/AuthContext";
import { errorMessage } from "../../utils/errors";
import { isValidTotpFormat } from "../../utils/validation";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Field, fieldDescribedBy } from "../ui/Field";

export function TotpForm() {
  const { pending, verifyTotp, cancelPending } = useAuth();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [goingBack, setGoingBack] = useState(false);
  const inFlight = useRef(false);
  const formatted = isValidTotpFormat(code);

  if (!pending) return null;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (inFlight.current) return;
    if (!formatted) {
      setError("El código debe tener exactamente seis dígitos.");
      return;
    }
    inFlight.current = true;
    setSubmitting(true);
    setError(null);
    try {
      await verifyTotp(code);
    } catch (submitError) {
      setError(
        errorMessage(
          submitError,
          "El código no es válido o la sesión temporal expiró. Intenta de nuevo.",
        ),
      );
      setCode("");
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  };

  const handleBack = async () => {
    setGoingBack(true);
    try {
      await cancelPending();
    } finally {
      setGoingBack(false);
    }
  };

  return (
    <div className="auth-card">
      <div className="auth-card__icon" aria-hidden="true">
        <ShieldCheck size={26} />
      </div>
      <div className="auth-card__heading">
        <p className="auth-card__eyebrow">Segundo factor</p>
        <h1>Verificación en dos pasos</h1>
        <p className="muted">
          Introduce el código de seis dígitos de Google Authenticator o Microsoft
          Authenticator para <strong>{pending.username}</strong>.
        </p>
      </div>

      {error ? (
        <Alert tone="danger" title="Código no aceptado" live>
          {error}
        </Alert>
      ) : null}

      <form className="auth-form" onSubmit={(event) => void handleSubmit(event)} noValidate>
        <Field
          id="totp-code"
          label="Código de verificación"
          required
          hint="El código cambia cada 30 segundos."
          error={error && !formatted ? "Introduce los seis dígitos." : undefined}
        >
          <div className="input-with-icon">
            <KeyRound aria-hidden="true" size={18} />
            <input
              id="totp-code"
              className="input totp-input"
              name="one-time-code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              value={code}
              onChange={(event) =>
                setCode(event.target.value.replace(/\D/g, "").slice(0, 6))
              }
              aria-invalid={code.length > 0 && !formatted ? true : undefined}
              aria-describedby={fieldDescribedBy(
                "totp-code",
                code.length > 0 && !formatted ? "error" : undefined,
                "hint",
              )}
              disabled={submitting}
              autoFocus
              required
            />
          </div>
        </Field>

        <Button
          type="submit"
          size="lg"
          fullWidth
          loading={submitting}
          loadingLabel="Verificando código…"
          disabled={!formatted}
          icon={<ShieldCheck aria-hidden="true" size={18} />}
        >
          Verificar y entrar
        </Button>
      </form>

      <Button
        variant="ghost"
        onClick={() => void handleBack()}
        loading={goingBack}
        loadingLabel="Volviendo…"
        icon={<ArrowLeft aria-hidden="true" size={17} />}
      >
        Volver al inicio de sesión
      </Button>

      <p className="auth-card__footnote small muted">
        La validación definitiva del código la realiza FastAPI. La sesión temporal
        expira automáticamente.
      </p>
    </div>
  );
}
