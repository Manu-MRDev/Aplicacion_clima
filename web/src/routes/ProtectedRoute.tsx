import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { LoadingBlock } from "../components/ui/Spinner";

export function ProtectedRoute() {
  const { status, startupError, retrySessionCheck } = useAuth();
  const location = useLocation();

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

  if (status !== "authenticated") {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    );
  }

  return <Outlet />;
}
