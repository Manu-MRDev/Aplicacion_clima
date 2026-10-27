import type { ButtonHTMLAttributes, ReactNode } from "react";

import { LoaderCircle } from "lucide-react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  loadingLabel?: string;
  icon?: ReactNode;
  iconAfter?: ReactNode;
  fullWidth?: boolean;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  loadingLabel = "Procesando…",
  icon,
  iconAfter,
  fullWidth = false,
  disabled,
  children,
  className = "",
  type = "button",
  ...props
}: ButtonProps) {
  const classes = [
    "button",
    `button--${variant}`,
    `button--${size}`,
    fullWidth ? "button--full" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      {...props}
      type={type}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      {loading ? (
        <LoaderCircle aria-hidden="true" className="button__spinner" size={18} />
      ) : (
        icon
      )}
      <span>{loading ? loadingLabel : children}</span>
      {!loading && iconAfter}
    </button>
  );
}
