import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import {
  CloudSun,
  DatabaseZap,
  History,
  LogOut,
  Menu,
  PlusCircle,
  ShieldCheck,
  X,
} from "lucide-react";

import { useAuth } from "../../contexts/AuthContext";
import { errorMessage } from "../../utils/errors";
import { Button } from "../ui/Button";
import { ConfirmDialog } from "../ui/ConfirmDialog";

const NAV_ITEMS = [
  { to: "/", label: "Panel", icon: CloudSun, end: true },
  { to: "/records", label: "Historial", icon: History, end: true },
  { to: "/records/new", label: "Nuevo registro", icon: PlusCircle, end: false },
  { to: "/integrity", label: "Integridad", icon: ShieldCheck, end: false },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
        menuButtonRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const handleLogout = async () => {
    setLoggingOut(true);
    setLogoutError(null);
    try {
      await logout();
      setConfirmOpen(false);
    } catch (error) {
      setLogoutError(
        errorMessage(error, "No se pudo cerrar la sesión. Intenta de nuevo."),
      );
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Saltar al contenido principal
      </a>
      <header className="site-header">
        <div className="container site-header__inner">
          <NavLink to="/" className="brand" aria-label="Clima, ir al panel">
            <span className="brand__mark" aria-hidden="true">
              <CloudSun size={24} />
            </span>
            <span className="brand__text">
              <strong>Clima</strong>
              <small>Observatorio de datos</small>
            </span>
          </NavLink>

          <button
            type="button"
            ref={menuButtonRef}
            className="nav-toggle"
            aria-expanded={menuOpen}
            aria-controls="primary-navigation"
            aria-label={menuOpen ? "Cerrar menú" : "Abrir menú"}
            onClick={() => setMenuOpen((value) => !value)}
          >
            {menuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
          </button>

          <nav
            id="primary-navigation"
            className={["primary-nav", menuOpen ? "primary-nav--open" : ""]
              .filter(Boolean)
              .join(" ")}
            aria-label="Navegación principal"
          >
            <ul className="primary-nav__list">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.end}
                      className={({ isActive }) =>
                        ["nav-link", isActive ? "nav-link--active" : ""]
                          .filter(Boolean)
                          .join(" ")
                      }
                      onClick={() => setMenuOpen(false)}
                    >
                      <Icon aria-hidden="true" size={17} />
                      {item.label}
                    </NavLink>
                  </li>
                );
              })}
            </ul>

            <div className="user-menu">
              <span className="user-chip" title="Usuario autenticado">
                <span className="user-chip__avatar" aria-hidden="true">
                  {user?.username.slice(0, 1).toUpperCase() ?? "?"}
                </span>
                <span className="user-chip__name">{user?.username}</span>
              </span>
              <Button
                variant="ghost"
                size="sm"
                icon={<LogOut aria-hidden="true" size={16} />}
                onClick={() => {
                  setLogoutError(null);
                  setConfirmOpen(true);
                  setMenuOpen(false);
                }}
              >
                Cerrar sesión
              </Button>
            </div>
          </nav>
        </div>
      </header>

      <main id="main-content" className="site-main" tabIndex={-1}>
        <Outlet />
      </main>

      <footer className="site-footer">
        <div className="container site-footer__inner">
          <span>
            Datos meteorológicos: Open-Meteo · Geocodificación: © OpenStreetMap
            contributors
          </span>
          <span className="site-footer__note">
            <DatabaseZap aria-hidden="true" size={15} /> Registros en PostgreSQL y SQL
            Server
          </span>
        </div>
      </footer>

      <ConfirmDialog
        open={confirmOpen}
        title="Cerrar sesión"
        description="Se revocará la sesión en el servidor y se borrarán los datos privados de esta pantalla."
        confirmLabel="Cerrar sesión"
        tone="danger"
        loading={loggingOut}
        error={logoutError}
        onCancel={() => {
          if (!loggingOut) setConfirmOpen(false);
        }}
        onConfirm={() => void handleLogout()}
      />
    </div>
  );
}
