import clsx from 'clsx';

export type StatusTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'primary';

const TONE_STYLES: Record<StatusTone, string> = {
  neutral: 'bg-white/65 text-text-secondary border-white/80 backdrop-blur-sm',
  success: 'bg-success-soft text-success border-success/20',
  warning: 'bg-warning-soft text-warning border-warning/20',
  danger: 'bg-danger-soft text-danger border-danger/20',
  info: 'bg-info-soft text-info border-info/20',
  primary: 'bg-primary-soft text-primary border-primary/20'
};

export function Badge({
  tone = 'neutral',
  className = '',
  children,
  ...rest
}: {
  tone?: StatusTone;
  className?: string;
  children: React.ReactNode;
} & React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-pill border px-2 py-0.5 text-metadata font-medium',
        TONE_STYLES[tone],
        className
      )}
      {...rest}
    >
      {children}
    </span>
  );
}

/**
 * Canonical ExamCraft status → visual tone mapping.
 * Use this instead of hand-picking colors per page.
 */
export const STATUS_TONE: Record<string, StatusTone> = {
  pending: 'warning',
  active: 'success',
  disabled: 'neutral',
  locked: 'neutral',
  generating: 'info',
  completed: 'success',
  failed: 'danger',
  success: 'success',
  warning: 'warning',
  error: 'danger',
  info: 'info',
  draft: 'neutral',
  approved: 'success',
  rejected: 'danger'
};

export function StatusBadge({
  status,
  className = ''
}: {
  /** One of STATUS_TONE keys, case-insensitive (e.g. 'pending', 'Generating'). */
  status: string;
  className?: string;
}) {
  const tone = STATUS_TONE[status.toLowerCase()] ?? 'neutral';
  return (
    <Badge tone={tone} className={className}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );
}
