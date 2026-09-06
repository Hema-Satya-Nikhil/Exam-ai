import clsx from 'clsx';
import type { HTMLAttributes, ReactNode } from 'react';

export function GlassSurface({
  as: Component = 'div',
  className = '',
  children,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { as?: 'div' | 'section' | 'article'; children: ReactNode }) {
  return (
    <Component className={clsx('glass-surface rounded-xl', className)} {...rest}>
      {children}
    </Component>
  );
}

export function GlassPanel({
  className = '',
  children,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { children: ReactNode }) {
  return (
    <div className={clsx('glass-surface rounded-2xl p-5 sm:p-6', className)} {...rest}>
      {children}
    </div>
  );
}
