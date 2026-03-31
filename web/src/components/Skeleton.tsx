/** Lightweight skeleton loading placeholder */
export function Skeleton({
  className = "",
  rows = 1,
  height = "h-4",
}: {
  className?: string;
  rows?: number;
  height?: string;
}) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={`skeleton ${height} ${i === rows - 1 && rows > 1 ? "w-3/5" : "w-full"}`}
        />
      ))}
    </div>
  );
}

/** Full-page loading skeleton */
export function PageSkeleton() {
  return (
    <div className="space-y-6 animate-fade-in">
      <Skeleton height="h-9" className="max-w-xs" />
      <Skeleton height="h-4" className="max-w-sm" />
      <div className="grid gap-4 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="glass-panel p-5 space-y-3">
            <Skeleton height="h-5" />
            <Skeleton height="h-3" rows={3} />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Slim inline spinner */
export function Spinner({ size = "sm" }: { size?: "sm" | "md" }) {
  const cls = size === "sm" ? "h-4 w-4 border-2" : "h-6 w-6 border-2";
  return (
    <span
      className={`inline-block ${cls} rounded-full border-current border-t-transparent animate-spin opacity-60`}
    />
  );
}
