import { LoaderCircle } from "lucide-react";

interface SpinnerProps {
  size?: number;
  label?: string;
  className?: string;
}

export function Spinner({ size = 22, label = "Cargando…", className = "" }: SpinnerProps) {
  return (
    <span className={["spinner", className].filter(Boolean).join(" ")} role="status">
      <LoaderCircle
        aria-hidden="true"
        size={size}
        className="spinner__icon"
      />
      <span className="visually-hidden">{label}</span>
    </span>
  );
}

export function LoadingBlock({ label = "Cargando…" }: { label?: string }) {
  return (
    <div className="loading-block" aria-live="polite">
      <Spinner label={label} />
      <p className="muted small">{label}</p>
    </div>
  );
}
