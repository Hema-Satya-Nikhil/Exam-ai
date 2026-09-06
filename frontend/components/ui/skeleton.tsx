import clsx from 'clsx';

/**
 * Skeleton loading placeholder. The pulse is decorative — pair with an
 * accessible loading announcement (role="status" text) for real waits.
 */
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={clsx(
        'animate-pulse rounded-sm bg-slate-200/80 motion-reduce:animate-none motion-reduce:bg-slate-200',
        className
      )}
    />
  );
}

/** Pre-composed skeleton for a list row (avatar/line/metadata). */
export function SkeletonList({ rows = 3, className = '' }: { rows?: number; className?: string }) {
  return (
    <div className={clsx('flex flex-col divide-y divide-line', className)} role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center justify-between gap-4 py-4">
          <div className="flex w-full flex-col gap-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="h-8 w-20 shrink-0" />
        </div>
      ))}
    </div>
  );
}
