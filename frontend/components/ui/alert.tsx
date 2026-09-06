import clsx from 'clsx';
import type { ReactNode } from 'react';

type AlertVariant = 'info' | 'success' | 'warning' | 'error';

const VARIANTS: Record<AlertVariant, { box: string; title: string }> = {
  info: { box: 'border-info/25 bg-info-soft', title: 'text-info' },
  success: { box: 'border-success/25 bg-success-soft', title: 'text-success' },
  warning: { box: 'border-warning/25 bg-warning-soft', title: 'text-warning' },
  error: { box: 'border-danger/25 bg-danger-soft', title: 'text-danger' }
};

const DEFAULT_TITLES: Record<AlertVariant, string> = {
  info: 'Information',
  success: 'Success',
  warning: 'Warning',
  error: 'Error'
};

/** Inline feedback banner. Use `error` for destructive failures. */
export function Alert({
  variant = 'info',
  title,
  className = '',
  children
}: {
  variant?: AlertVariant;
  /** Defaults to a variant-appropriate title. */
  title?: string;
  className?: string;
  children: ReactNode;
}) {
  const v = VARIANTS[variant];
  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      className={clsx('rounded-md border px-4 py-3 text-small', v.box, className)}
    >
      <p className={clsx('font-semibold', v.title)}>{title ?? DEFAULT_TITLES[variant]}</p>
      {children ? <div className="mt-1 text-text-secondary">{children}</div> : null}
    </div>
  );
}
