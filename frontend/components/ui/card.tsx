import clsx from 'clsx';
import type { ReactNode } from 'react';

/**
 * Card system — subtle border, restrained elevation, consistent padding.
 * Avoid heavy shadows/blur; `elevated` is opt-in for overlays on cards.
 */
export function Card({
  className = '',
  elevated = false,
  children
}: {
  className?: string;
  elevated?: boolean;
  children: ReactNode;
}) {
  return (
    <div
      className={clsx(
        'rounded-xl border border-white/70 bg-white/70 shadow-glass-soft backdrop-blur-glass',
        elevated ? 'shadow-high' : '',
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className = '', children }: { className?: string; children: ReactNode }) {
  return <div className={clsx('flex flex-col gap-1 px-5 pt-5 pb-4', className)}>{children}</div>;
}

export function CardTitle({
  id,
  className = '',
  children
}: {
  id?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <h3 id={id} className={clsx('text-section-heading text-text-primary', className)}>
      {children}
    </h3>
  );
}

export function CardDescription({ className = '', children }: { className?: string; children: ReactNode }) {
  return <p className={clsx('text-small text-text-secondary', className)}>{children}</p>;
}

export function CardContent({ className = '', children }: { className?: string; children: ReactNode }) {
  return <div className={clsx('px-5 pb-5 text-body text-text-secondary', className)}>{children}</div>;
}

export function CardFooter({ className = '', children }: { className?: string; children: ReactNode }) {
  return (
    <div className={clsx('flex flex-wrap items-center gap-3 border-t border-line px-5 py-4', className)}>
      {children}
    </div>
  );
}
