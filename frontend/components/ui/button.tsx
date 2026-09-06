import clsx from 'clsx';
import Link from 'next/link';
import type { ReactNode } from 'react';

import { Spinner } from './spinner';

type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

const VARIANTS: Record<ButtonVariant, string> = {
  // Primary action — one per view wherever possible
  primary:
    'bg-primary text-white shadow-low hover:bg-primary-hover active:scale-[0.98] active:bg-primary-hover disabled:bg-primary/50',
  // Secondary — solid neutral
  secondary:
    'bg-white/70 text-text-primary border border-white/80 shadow-low backdrop-blur-sm hover:bg-white/90 active:scale-[0.98] disabled:text-text-muted disabled:bg-slate-50',
  // Outline — brand-tinted quiet action
  outline:
    'bg-white/35 text-primary border border-primary/30 backdrop-blur-sm hover:bg-primary-soft/60 active:scale-[0.98] active:bg-primary-soft disabled:border-line disabled:text-text-muted',
  // Ghost — tertiary / low-emphasis
  ghost:
    'bg-white/25 text-text-secondary hover:bg-white/65 active:scale-[0.98] active:bg-slate-200 disabled:text-text-muted',
  // Destructive
  danger:
    'bg-danger text-white shadow-low hover:bg-red-700 active:scale-[0.98] active:bg-red-700 disabled:bg-danger/50'
};

const SIZES: Record<ButtonSize, string> = {
  sm: 'h-8 gap-1.5 px-3 text-small rounded-[0.5rem]',
  md: 'h-10 gap-2 px-4 text-small rounded-[0.5rem]',
  lg: 'h-11 gap-2 px-5 text-body rounded-[0.625rem]'
};

export function buttonClasses(options: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  className?: string;
}): string {
  const { variant = 'primary', size = 'md', fullWidth = false, className = '' } = options;
  return clsx(
    'inline-flex select-none items-center justify-center font-medium transition-all duration-micro ease-standard focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed',
    VARIANTS[variant],
    SIZES[size],
    fullWidth && 'w-full',
    className
  );
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a spinner and disables the button (e.g. Save Changes → Saving…). */
  loading?: boolean;
  loadingText?: string;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
  fullWidth?: boolean;
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  loadingText,
  leadingIcon,
  trailingIcon,
  fullWidth = false,
  disabled,
  className = '',
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <button
      {...rest}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={buttonClasses({ variant, size, fullWidth, className })}
    >
      {loading ? (
        <>
          <Spinner className="h-4 w-4" />
          <span>{loadingText ?? 'Saving…'}</span>
        </>
      ) : (
        <>
          {leadingIcon ? <span className="inline-flex shrink-0 [&>svg]:h-4 [&>svg]:w-4">{leadingIcon}</span> : null}
          <span>{children}</span>
          {trailingIcon ? <span className="inline-flex shrink-0 [&>svg]:h-4 [&>svg]:w-4">{trailingIcon}</span> : null}
        </>
      )}
    </button>
  );
}

/** Same visual system as Button, rendering a Next.js Link for navigation CTAs. */
export function ButtonLink({
  href,
  variant = 'primary',
  size = 'md',
  leadingIcon,
  trailingIcon,
  fullWidth = false,
  className = '',
  children,
  ...rest
}: {
  href: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
  fullWidth?: boolean;
  className?: string;
  children: ReactNode;
} & Omit<React.ComponentProps<typeof Link>, 'href' | 'className' | 'children'>) {
  return (
    <Link
      {...rest}
      href={href as Parameters<typeof Link>[0]['href']}
      className={buttonClasses({ variant, size, fullWidth, className })}
    >
      {leadingIcon ? <span className="inline-flex shrink-0 [&>svg]:h-4 [&>svg]:w-4">{leadingIcon}</span> : null}
      <span>{children}</span>
      {trailingIcon ? <span className="inline-flex shrink-0 [&>svg]:h-4 [&>svg]:w-4">{trailingIcon}</span> : null}
    </Link>
  );
}


export interface IconButtonProps extends Omit<ButtonProps, 'leadingIcon' | 'trailingIcon' | 'fullWidth'> {
  /** Required: icon-only buttons must be labelled for screen readers. */
  'aria-label': string;
  children: ReactNode;
}

/** Icon-only button — accessible name is mandatory. */
export function IconButton({ size = 'md', variant = 'ghost', className = '', children, ...rest }: IconButtonProps) {
  const iconSizes: Record<ButtonSize, string> = {
    sm: 'h-8 w-8 [&>svg]:h-4 [&>svg]:w-4',
    md: 'h-10 w-10 [&>svg]:h-[18px] [&>svg]:w-[18px]',
    lg: 'h-11 w-11 [&>svg]:h-5 [&>svg]:w-5'
  };
  return (
    <Button
      {...rest}
      size={size}
      variant={variant}
      className={`!px-0 ${iconSizes[size]} ${className}`}
    >
      {children}
    </Button>
  );
}
