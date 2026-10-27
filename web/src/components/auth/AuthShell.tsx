import type { ReactNode } from "react";

import { CloudSun, Database, MapPin, ShieldCheck, Wind } from "lucide-react";

interface AuthShellProps {
  children: ReactNode;
}

export function AuthShell({ children }: AuthShellProps) {
  return (
    <div className="auth-shell">
      <aside className="auth-hero">
        <div className="auth-hero__brand">
          <span className="brand__mark" aria-hidden="true">
            <CloudSun size={26} />
          </span>
          <div>
            <strong>Clima</strong>
            <p>Observatorio de datos</p>
          </div>
        </div>

        <div className="auth-hero__content">
          <p className="auth-hero__eyebrow">Meteorología + trazabilidad</p>
          <h2>Consulta el clima y deja registro de cada observación.</h2>
          <p>
            Una interfaz para consultar Open-Meteo, guardar mediciones en dos servidores
            independientes y verificar la integridad de los datos.
          </p>

          <ul className="auth-hero__features">
            <li>
              <MapPin aria-hidden="true" size={19} />
              <span>Ubicación actual o coordenadas seleccionadas.</span>
            </li>
            <li>
              <Database aria-hidden="true" size={19} />
              <span>Registros separados en PostgreSQL y SQL Server.</span>
            </li>
            <li>
              <ShieldCheck aria-hidden="true" size={19} />
              <span>Verificación de cadenas de hashes desde FastAPI.</span>
            </li>
            <li>
              <Wind aria-hidden="true" size={19} />
              <span>Acceso protegido con contraseña y TOTP.</span>
            </li>
          </ul>
        </div>

        <p className="auth-hero__footer small">
          Los datos meteorológicos provienen de Open-Meteo. La geocodificación inversa
          utiliza © OpenStreetMap contributors.
        </p>
        <div className="auth-hero__orb" aria-hidden="true" />
      </aside>

      <main className="auth-main">
        <div className="auth-main__inner">{children}</div>
      </main>
    </div>
  );
}
