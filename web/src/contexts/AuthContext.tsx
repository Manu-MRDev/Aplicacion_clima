import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { AUTH_EXPIRED_EVENT } from "../config";
import * as authService from "../services/auth";
import { ApiError } from "../services/apiClient";
import type {
  AuthenticatedResponse,
  EnrollmentResponse,
  LoginChallengeStatus,
  LoginCredentials,
  LoginResponse,
  RegisterCredentials,
  RegistrationResponse,
  User,
} from "../types/auth";

export type AuthStatus =
  | "checking"
  | "anonymous"
  | "pending"
  | "authenticated"
  | "unavailable";

export interface PendingAuth {
  status: LoginChallengeStatus;
  username: string;
  csrfToken: string;
  expiresAt: string;
  message: string;
}

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  csrfToken: string | null;
  pending: PendingAuth | null;
  sessionExpiresAt: string | null;
  sessionExpired: boolean;
  startupError: string | null;
  login: (credentials: LoginCredentials) => Promise<LoginResponse>;
  register: (credentials: RegisterCredentials) => Promise<RegistrationResponse>;
  verifyTotp: (code: string) => Promise<void>;
  enrollTotp: () => Promise<EnrollmentResponse>;
  confirmTotp: (code: string) => Promise<void>;
  logout: () => Promise<void>;
  cancelPending: () => Promise<void>;
  retrySessionCheck: () => void;
  refreshCsrf: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function applyAuthenticated(
  response: AuthenticatedResponse,
): Pick<
  AuthContextValue,
  "status" | "user" | "csrfToken" | "pending" | "sessionExpiresAt"
> {
  return {
    status: "authenticated",
    user: response.user,
    csrfToken: response.csrf_token,
    pending: null,
    sessionExpiresAt: response.session_expires_at,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("checking");
  const [user, setUser] = useState<User | null>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAuth | null>(null);
  const [sessionExpiresAt, setSessionExpiresAt] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [startupError, setStartupError] = useState<string | null>(null);
  const [checkAttempt, setCheckAttempt] = useState(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const clearSession = useCallback(() => {
    setStatus("anonymous");
    setUser(null);
    setCsrfToken(null);
    setPending(null);
    setSessionExpiresAt(null);
  }, []);

  const checkSession = useCallback(async () => {
    setStatus("checking");
    setStartupError(null);
    const controller = new AbortController();
    try {
      const response = await authService.getCurrentUser(controller.signal);
      if (!mounted.current) return;
      setStatus("authenticated");
      setUser(response.user);
      setCsrfToken(response.csrf_token);
      setSessionExpiresAt(response.session_expires_at);
      setPending(null);
    } catch (error) {
      if (!mounted.current) return;
      if (error instanceof ApiError && error.status === 401) {
        clearSession();
        setSessionExpired(false);
        return;
      }
      setStatus("unavailable");
      setStartupError(
        error instanceof Error
          ? error.message
          : "No se pudo comprobar la sesión con el servidor.",
      );
    }
  }, [clearSession]);

  useEffect(() => {
    void checkSession();
  }, [checkSession, checkAttempt]);

  useEffect(() => {
    const onExpired = () => {
      setSessionExpired(true);
      clearSession();
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, [clearSession]);

  const acceptChallenge = useCallback(
    (
      response: Pick<
        LoginResponse,
        "status" | "csrf_token" | "expires_at" | "message"
      >,
      username: string,
    ) => {
      setStatus("pending");
      setPending({
        status: response.status,
        username: username.trim(),
        csrfToken: response.csrf_token,
        expiresAt: response.expires_at,
        message: response.message,
      });
      setSessionExpired(false);
      setStartupError(null);
    },
    [],
  );

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      const response = await authService.login(credentials);
      acceptChallenge(response, credentials.username);
      return response;
    },
    [acceptChallenge],
  );

  const register = useCallback(
    async (credentials: RegisterCredentials) => {
      const response = await authService.register(credentials);
      acceptChallenge(response, credentials.username);
      return response;
    },
    [acceptChallenge],
  );

  const verifyTotp = useCallback(
    async (code: string) => {
      if (!pending) {
        throw new Error("No hay una verificación TOTP en curso.");
      }
      const response = await authService.verifyTotp(code, pending.csrfToken);
      const next = applyAuthenticated(response);
      setStatus(next.status);
      setUser(next.user);
      setCsrfToken(next.csrfToken);
      setPending(next.pending);
      setSessionExpiresAt(next.sessionExpiresAt);
      setSessionExpired(false);
    },
    [pending],
  );

  const enrollTotp = useCallback(async () => {
    if (!pending) {
      throw new Error("No hay una inscripción TOTP en curso.");
    }
    return authService.enrollTotp(pending.csrfToken);
  }, [pending]);

  const confirmTotp = useCallback(
    async (code: string) => {
      if (!pending) {
        throw new Error("No hay una inscripción TOTP en curso.");
      }
      const response = await authService.confirmTotp(code, pending.csrfToken);
      const next = applyAuthenticated(response);
      setStatus(next.status);
      setUser(next.user);
      setCsrfToken(next.csrfToken);
      setPending(next.pending);
      setSessionExpiresAt(next.sessionExpiresAt);
      setSessionExpired(false);
    },
    [pending],
  );

  const refreshCsrf = useCallback(async () => {
    if (status !== "authenticated") return null;
    try {
      const response = await authService.getCurrentUser();
      setUser(response.user);
      setCsrfToken(response.csrf_token);
      setSessionExpiresAt(response.session_expires_at);
      return response.csrf_token;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setSessionExpired(true);
        clearSession();
        return null;
      }
      throw error;
    }
  }, [clearSession, status]);

  const logout = useCallback(async () => {
    const token = csrfToken;
    if (!token) {
      clearSession();
      setSessionExpired(false);
      return;
    }
    try {
      await authService.logout(token);
      clearSession();
      setSessionExpired(false);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearSession();
        setSessionExpired(false);
        return;
      }
      if (error instanceof ApiError && error.status === 403 && status === "authenticated") {
        const refreshed = await refreshCsrf();
        if (refreshed) {
          await authService.logout(refreshed);
          clearSession();
          setSessionExpired(false);
        }
        // Si el refresco devolvió null, la sesión ya se limpió o dejó de ser
        // válida; no hay nada más que revocar desde este navegador.
        return;
      }
      if (error instanceof ApiError && error.status === 403 && status === "pending") {
        // La sesión pendiente no permite completar el cierre; no concede acceso.
        clearSession();
        setSessionExpired(false);
        return;
      }
      throw error;
    }
  }, [clearSession, csrfToken, refreshCsrf, status]);

  const cancelPending = useCallback(async () => {
    const token = pending?.csrfToken;
    if (token) {
      try {
        await authService.logout(token);
      } catch {
        // La sesión pendiente no concede acceso. Se limpia el estado local igualmente.
      }
    }
    clearSession();
    setSessionExpired(false);
  }, [clearSession, pending]);

  const retrySessionCheck = useCallback(() => {
    setCheckAttempt((value) => value + 1);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      csrfToken,
      pending,
      sessionExpiresAt,
      sessionExpired,
      startupError,
      login,
      register,
      verifyTotp,
      enrollTotp,
      confirmTotp,
      logout,
      cancelPending,
      retrySessionCheck,
      refreshCsrf,
    }),
    [
      cancelPending,
      confirmTotp,
      csrfToken,
      enrollTotp,
      login,
      logout,
      pending,
      refreshCsrf,
      register,
      retrySessionCheck,
      sessionExpired,
      sessionExpiresAt,
      startupError,
      status,
      user,
      verifyTotp,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth debe usarse dentro de AuthProvider");
  }
  return value;
}
