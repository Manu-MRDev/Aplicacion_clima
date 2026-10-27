import { apiRequest } from "./apiClient";
import type {
  AuthenticatedResponse,
  EnrollmentResponse,
  LoginCredentials,
  LoginResponse,
  LogoutResponse,
  MeResponse,
  RegisterCredentials,
  RegistrationResponse,
} from "../types/auth";

export function login(credentials: LoginCredentials, signal?: AbortSignal) {
  return apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: credentials,
    signal,
    suppressAuthEvent: true,
  });
}

export function register(credentials: RegisterCredentials, signal?: AbortSignal) {
  return apiRequest<RegistrationResponse>("/auth/register", {
    method: "POST",
    body: credentials,
    signal,
    suppressAuthEvent: true,
  });
}

export function verifyTotp(code: string, csrfToken: string, signal?: AbortSignal) {
  return apiRequest<AuthenticatedResponse>("/auth/totp/verify", {
    method: "POST",
    body: { code },
    csrfToken,
    signal,
    suppressAuthEvent: true,
  });
}

export function enrollTotp(csrfToken: string, signal?: AbortSignal) {
  return apiRequest<EnrollmentResponse>("/auth/totp/enroll", {
    method: "POST",
    csrfToken,
    signal,
    suppressAuthEvent: true,
  });
}

export function confirmTotp(code: string, csrfToken: string, signal?: AbortSignal) {
  return apiRequest<AuthenticatedResponse>("/auth/totp/confirm", {
    method: "POST",
    body: { code },
    csrfToken,
    signal,
    suppressAuthEvent: true,
  });
}

export function getCurrentUser(signal?: AbortSignal) {
  return apiRequest<MeResponse>("/auth/me", {
    signal,
    suppressAuthEvent: true,
  });
}

export function logout(csrfToken: string, signal?: AbortSignal) {
  return apiRequest<LogoutResponse>("/auth/logout", {
    method: "POST",
    csrfToken,
    signal,
    suppressAuthEvent: true,
  });
}
