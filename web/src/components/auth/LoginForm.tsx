import { useRef, useState, type FormEvent } from "react";

import { Link } from "react-router-dom";

import { Eye, EyeOff, LockKeyhole, LogIn, UserRound } from "lucide-react";

import { useAuth } from "../../contexts/AuthContext";
import { errorMessage } from "../../utils/errors";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Field, fieldDescribedBy } from "../ui/Field";

interface LoginFormProps {
  sessionExpired: boolean;
}

export function LoginForm({ sessionExpired }: LoginFormProps) {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ username?: string; password?: string }>(
    {},
  );
  const inFlight = useRef(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (inFlight.current) return;

    const nextErrors: { username?: string; password?: string } = {};
    if (!username.trim()) nextErrors.username = "Introduce tu nombre de usuario.";
    else if (username.trim().length > 64) nextErrors.username = "Máximo 64 caracteres.";
    if (!password) nextErrors.password = "Introduce tu contraseña.";
    else if (password.length > 512) nextErrors.password = "Máximo 512 caracteres.";
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    inFlight.current = true;
    setSubmitting(true);
    setError(null);
    try {
      await login({ username: username.trim(), password });
    } catch (submitError) {
      setError(
        errorMessage(
          submitError,
          "No fue posible iniciar sesión. Verifica tus credenciales.",
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
        <p className="auth-card__eyebrow">Acceso seguro</p>
        <h1>Inicia sesión</h1>
        <p className="muted">
          Autenticación en dos pasos con tu aplicación autenticadora.
        </p>
      </div>

      {sessionExpired ? (
        <Alert tone="warning" title="La sesión terminó" live>
          Tu sesión expiró o fue revocada. Vuelve a iniciar sesión para continuar.
        </Alert>
      ) : null}

      {error ? (
        <Alert tone="danger" title="No se pudo iniciar sesión" live>
          {error}
        </Alert>
      ) : null}

      <form className="auth-form" onSubmit={(event) => void handleSubmit(event)} noValidate>
        <Field
          id="login-username"
          label="Nombre de usuario"
          required
          error={fieldErrors.username}
        >
          <div className="input-with-icon">
            <UserRound aria-hidden="true" size={18} />
            <input
              id="login-username"
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
              aria-describedby={fieldDescribedBy("login-username", fieldErrors.username)}
              disabled={submitting}
              required
            />
          </div>
        </Field>

        <Field
          id="login-password"
          label="Contraseña"
          required
          error={fieldErrors.password}
        >
          <div className="input-with-icon input-with-icon--action">
            <LockKeyhole aria-hidden="true" size={18} />
            <input
              id="login-password"
              className="input"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              maxLength={512}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-invalid={fieldErrors.password ? true : undefined}
              aria-describedby={fieldDescribedBy("login-password", fieldErrors.password)}
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

        <Button
          type="submit"
          size="lg"
          fullWidth
          loading={submitting}
          loadingLabel="Verificando credenciales…"
          icon={<LogIn aria-hidden="true" size={18} />}
        >
          Continuar
        </Button>
      </form>

      <p className="auth-card__switch small">
        ¿No tienes una cuenta? <Link to="/register">Crear una cuenta</Link>
      </p>

      <p className="auth-card__footnote small muted">
        La contraseña se envía directamente a FastAPI y no se guarda en este
        navegador. Después se solicitará el código de seis dígitos.
      </p>
    </div>
  );
}
