export function Skeleton({ className = "" }: { className?: string }) {
  return <span className={["skeleton", className].filter(Boolean).join(" ")} aria-hidden="true" />;
}

export function CardSkeleton() {
  return (
    <div className="card skeleton-card" aria-hidden="true">
      <Skeleton className="skeleton--line skeleton--w40" />
      <Skeleton className="skeleton--title" />
      <Skeleton className="skeleton--line skeleton--w70" />
      <Skeleton className="skeleton--line skeleton--w55" />
    </div>
  );
}
