import type { ReactNode } from "react";

interface BadgeProps {
  tone?: "success" | "warning" | "danger" | "neutral" | "info" | "accent";
  children: ReactNode;
  icon?: ReactNode;
  className?: string;
}

export function Badge({ tone = "neutral", children, icon, className = "" }: BadgeProps) {
  return (
    <span className={["badge", `badge--${tone}`, className].filter(Boolean).join(" ")}>
      {icon}
      {children}
    </span>
  );
}
