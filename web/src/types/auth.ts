export interface User {
  id: number;
  username: string;
  totp_enabled: boolean;
  created_at: string | null;
}

export type LoginChallengeStatus = "totp_required" | "enrollment_required";

export interface LoginResponse {
  status: LoginChallengeStatus;
  csrf_token: string;
  expires_at: string;
  message: string;
}

export interface EnrollmentResponse {
  manual_key: string;
  otpauth_uri: string;
  qr_data_uri: string;
  issuer: string;
  account: string;
  expires_at: string;
  message: string;
}

export interface AuthenticatedResponse {
  status: "authenticated";
  user: User;
  csrf_token: string;
  session_expires_at: string;
}

export interface MeResponse {
  user: User;
  csrf_token: string;
  session_expires_at: string;
}

export interface LogoutResponse {
  status: "logged_out";
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterCredentials {
  username: string;
  password: string;
}

export interface RegistrationResponse {
  status: "enrollment_required";
  csrf_token: string;
  expires_at: string;
  message: string;
}

export interface TotpCode {
  code: string;
}
