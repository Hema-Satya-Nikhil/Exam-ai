import clsx from 'clsx';
import type { ReactNode } from 'react';

import { Button, type ButtonProps } from './button';

/**
 * Empty state — icon, clear title, short explanation, one action.
 * Used for empty lists, no search results, first-run views.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
  actionLabel,
  onAction,
  actionVariant = 'primary',
  className = ''
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  /** Pre-built action node wins over actionLabel/onAction. */
  action?: ReactNode;
  actionLabel?: string;
  onAction?: ButtonProps['onClick'];
  actionVariant?: ButtonProps['variant'];
  className?: string;
}) {
  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center rounded-lg border border-dashed border-line bg-surface/60 px-6 py-12 text-center',
        className
      )}
    >
      {icon ? (
        <div className="[&>svg]:h-10 [&>svg]:w-10 text-text-muted [&>svg]:mx-auto" aria-hidden="true">
          {icon}
        </div>
      ) : null}
      <p className="mt-3 text-body font-medium text-text-primary">{title}</p>
      {description ? (
        <p className="mt-1 max-w-sm text-small leading-6 text-text-secondary">{description}</p>
      ) : null}
      {action ? (
        <div className="mt-5">{action}</div>
      ) : actionLabel && onAction ? (
        <div className="mt-5">
          <Button variant={actionVariant} onClick={onAction}>
            {actionLabel}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
