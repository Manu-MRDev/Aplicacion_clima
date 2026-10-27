import type { ReactNode } from "react";

import {
  AlertCircle,
  CheckCircle2,
  Info,
  TriangleAlert,
} from "lucide-react";

import type { VisualTone } from "../../utils/errors";

interface AlertProps {
  tone?: VisualTone;
  title?: string;
  children: ReactNode;
  actions?: ReactNode;
  className?: string;
  live?: boolean;
}

const ICONS = {
  success: CheckCircle2,
  warning: TriangleAlert,
  danger: AlertCircle,
  info: Info,
  neutral: Info,
};

export function Alert({
  tone = "info",
  title,
  children,
  actions,
  className = "",
  live = false,
}: AlertProps) {
  const Icon = ICONS[tone];
  return (
    <div
      className={["alert", `alert--${tone}`, className].filter(Boolean).join(" ")}
      role={live ? "status" : undefined}
      aria-live={live ? "polite" : undefined}
    >
      <Icon aria-hidden="true" size={20} className="alert__icon" />
      <div className="alert__body">
        {title ? <p className="alert__title">{title}</p> : null}
        <div className="alert__message">{children}</div>
      </div>
      {actions ? <div className="alert__actions">{actions}</div> : null}
    </div>
  );
}
