import { useRef, useState, type FormEvent } from "react";

import { Link } from "react-router-dom";

import {
  Eye,
  EyeOff,
  LockKeyhole,
  ShieldCheck,
  UserPlus,
  UserRound,
} from "lucide-react";

import { useAuth } from "../../contexts/AuthContext";
import { ApiError } from "../../services/apiClient";
import { errorMessage } from "../../utils/errors";
import {
  mapAuthFieldErrors,
  validateRegistration,
  type FieldErrors,
} from "../../utils/validation";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Field, fieldDescribedBy } from "../ui/Field";

type RegistrationFieldErrors = FieldErrors & {
  username?: string;
  password?: string;
  confirmPassword?: string;
};

export function RegisterForm() {
  const { register } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<RegistrationFieldErrors>({});
  const inFlight = useRef(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (inFlight.current) return;

    setError(null);
    const validation = validateRegistration({
      username,
      password,
      confirmPassword,
    });
    setFieldErrors(validation.errors);
    if (!validation.values) return;

    inFlight.current = true;
    setSubmitting(true);
    try {
      await register(validation.values);
    } catch (submitError) {
      if (submitError instanceof ApiError && submitError.status === 422) {
        const apiErrors = mapAuthFieldErrors(submitError.details?.errors);
        if (Object.keys(apiErrors).length > 0) {
          setFieldErrors(apiErrors);
        }
      }
      setError(
        errorMessage(
          submitError,
          "No fue posible crear la cuenta. Intenta de nuevo.",
        ),
      );
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-card">
      <div className="auth-card__heading">
        <p className="auth-card__eyebrow">Cuenta nueva</p>
        <h1>Crea tu cuenta</h1>
        <p className="muted">
          Después de crearla configurarás el segundo factor con una aplicación
          autenticadora.
        </p>
      </div>

      {error ? (
        <Alert tone="danger" title="No se pudo crear la cuenta" live>
          {error}
        </Alert>
      ) : null}

      <form className="auth-form" onSubmit={(event) => void handleSubmit(event)} noValidate>
        <Field
          id="register-username"
          label="Nombre de usuario"
          required
          error={fieldErrors.username}
          hint="De 3 a 64 caracteres: letras, números, punto, guion o guion bajo."
        >
          <div className="input-with-icon">
            <UserRound aria-hidden="true" size={18} />
            <input
              id="register-username"
              className="input"
              name="username"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              maxLength={64}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              aria-invalid={fieldErrors.username ? true : undefined}
              aria-describedby={fieldDescribedBy(
                "register-username",
                fieldErrors.username,
                "hint",
              )}
              disabled={submitting}
              autoFocus
              required
            />
          </div>
        </Field>

        <Field
          id="register-password"
          label="Contraseña"
          required
          error={fieldErrors.password}
          hint="Mínimo 12 caracteres. Combina al menos tres tipos: minúsculas, mayúsculas, números y símbolos."
        >
          <div className="input-with-icon input-with-icon--action">
            <LockKeyhole aria-hidden="true" size={18} />
            <input
              id="register-password"
              className="input"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              maxLength={128}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-invalid={fieldErrors.password ? true : undefined}
              aria-describedby={fieldDescribedBy(
                "register-password",
                fieldErrors.password,
                "hint",
              )}
              disabled={submitting}
              required
            />
            <button
              type="button"
              className="input-action"
              onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
              aria-pressed={showPassword}
            >
              {showPassword ? (
                <EyeOff aria-hidden="true" size={18} />
              ) : (
                <Eye aria-hidden="true" size={18} />
              )}
            </button>
          </div>
        </Field>

        <Field
          id="register-confirm-password"
          label="Repite la contraseña"
          required
          error={fieldErrors.confirmPassword}
        >
          <div className="input-with-icon input-with-icon--action">
            <ShieldCheck aria-hidden="true" size={18} />
            <input
              id="register-confirm-password"
              className="input"
              name="confirmPassword"
              type={showConfirmation ? "text" : "password"}
              autoComplete="new-password"
              maxLength={128}
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              aria-invalid={fieldErrors.confirmPassword ? true : undefined}
              aria-describedby={fieldDescribedBy(
                "register-confirm-password",
                fieldErrors.confirmPassword,
              )}
              disabled={submitting}
              required
            />
            <button
              type="button"
              className="input-action"
              onClick={() => setShowConfirmation((value) => !value)}
              aria-label={
                showConfirmation ? "Ocultar confirmación" : "Mostrar confirmación"
              }
              aria-pressed={showConfirmation}
            >
              {showConfirmation ? (
                <EyeOff aria-hidden="true" size={18} />
              ) : (
                <Eye aria-hidden="true" size={18} />
              )}
            </button>
          </div>
        </Field>

        <Button
          type="submit"
          size="lg"
          fullWidth
          loading={submitting}
          loadingLabel="Creando cuenta…"
          icon={<UserPlus aria-hidden="true" size={18} />}
        >
          Crear cuenta
        </Button>
      </form>

      <p className="auth-card__switch small">
        ¿Ya tienes una cuenta? <Link to="/login">Inicia sesión</Link>
      </p>

      <p className="auth-card__footnote small muted">
        La contraseña se envía directamente a FastAPI y no se guarda en este
        navegador. El secreto TOTP se genera y cifra en el backend.
      </p>
    </div>
  );
}
