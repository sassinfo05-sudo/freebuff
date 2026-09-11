export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton animate-shimmer rounded-md ${className}`} />;
}

export function SkeletonRows({ count = 3, className = "" }: { count?: number; className?: string }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full rounded-lg" />
      ))}
    </div>
  );
}
