import type { ReactNode } from "react";

import { Inbox } from "lucide-react";

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <span className="empty-state__icon" aria-hidden="true">
        {icon ?? <Inbox size={26} />}
      </span>
      <h3>{title}</h3>
      {description ? <p className="muted">{description}</p> : null}
      {action ? <div className="empty-state__action">{action}</div> : null}
    </div>
  );
}
