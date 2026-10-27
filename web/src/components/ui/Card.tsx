import type { HTMLAttributes, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  as?: "div" | "section" | "article";
  tone?: "default" | "soft" | "accent";
}

export function Card({
  as: Component = "div",
  tone = "default",
  className = "",
  children,
  ...props
}: CardProps) {
  return (
    <Component
      className={["card", `card--${tone}`, className].filter(Boolean).join(" ")}
      {...props}
    >
      {children}
    </Component>
  );
}
