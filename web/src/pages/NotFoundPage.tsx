import { Link } from "react-router-dom";

import { CloudOff } from "lucide-react";

export function NotFoundPage() {
  return (
    <div className="full-page-state">
      <div className="full-page-state__panel">
        <span className="not-found__icon" aria-hidden="true">
          <CloudOff size={34} />
        </span>
        <p className="page-header__eyebrow">Error 404</p>
        <h1>Esta página no existe</h1>
        <p className="muted">
          La dirección no corresponde a ninguna sección de la aplicación.
        </p>
        <div className="cluster">
          <Link to="/" className="button button--primary button--md">
            Ir al panel
          </Link>
          <Link to="/login" className="button button--secondary button--md">
            Iniciar sesión
          </Link>
        </div>
      </div>
    </div>
  );
}
