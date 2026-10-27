import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";
import { AuthShell } from "../components/auth/AuthShell";
import { EnrollmentPanel } from "../components/auth/EnrollmentPanel";
import { LoginForm } from "../components/auth/LoginForm";
import { TotpForm } from "../components/auth/TotpForm";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { LoadingBlock } from "../components/ui/Spinner";

interface LoginLocationState {
  from?: string;
}

export function LoginPage() {
  const {
    status,
    pending,
    sessionExpired,
    startupError,
    retrySessionCheck,
  } = useAuth();
  const location = useLocation();
  const requestedFrom = (location.state as LoginLocationState | null)?.from;
  const destination =
    requestedFrom && requestedFrom.startsWith("/") && !requestedFrom.startsWith("/login")
      ? requestedFrom
      : "/";

  if (status === "authenticated") {
    return <Navigate to={destination} replace />;
  }

  if (status === "checking") {
    return (
      <div className="full-page-state" aria-busy="true">
        <LoadingBlock label="Comprobando la sesión…" />
      </div>
    );
  }

  if (status === "unavailable") {
    return (
      <div className="full-page-state">
        <div className="full-page-state__panel">
          <h1>No se pudo comprobar la sesión</h1>
          <Alert tone="danger" title="Sin conexión con la API">
            {startupError ?? "Verifica que el backend esté disponible e intenta de nuevo."}
          </Alert>
          <Button onClick={retrySessionCheck}>Reintentar</Button>
        </div>
      </div>
    );
  }

  return (
    <AuthShell>
      {status === "pending" && pending ? (
        pending.status === "totp_required" ? (
          <TotpForm />
        ) : (
          <EnrollmentPanel />
        )
      ) : (
        <LoginForm sessionExpired={sessionExpired} />
      )}
    </AuthShell>
  );
}
