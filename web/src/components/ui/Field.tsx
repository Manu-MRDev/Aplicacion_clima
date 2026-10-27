import type { ReactNode } from "react";

interface FieldProps {
  id: string;
  label: string;
  error?: string;
  hint?: ReactNode;
  required?: boolean;
  children: ReactNode;
  className?: string;
}

export function Field({
  id,
  label,
  error,
  hint,
  required = false,
  children,
  className = "",
}: FieldProps) {
  return (
    <div className={["field", error ? "field--invalid" : "", className].filter(Boolean).join(" ")}>
      <label className="field__label" htmlFor={id}>
        {label}
        {required ? <span className="field__required" aria-hidden="true"> *</span> : null}
      </label>
      {children}
      {hint ? (
        <p className="field__hint" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
      {error ? (
        <p className="field__error" id={`${id}-error`} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function fieldDescribedBy(id: string, error?: string, hint?: string): string | undefined {
  const ids = [hint ? `${id}-hint` : "", error ? `${id}-error` : ""].filter(Boolean);
  return ids.length ? ids.join(" ") : undefined;
}
