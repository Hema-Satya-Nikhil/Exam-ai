'use client';

import clsx from 'clsx';
import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';

import { IconButton } from './button';
import { X } from 'lucide-react';

/**
 * Dialog/modal foundation.
 * - role="dialog" + aria-modal, labelled by the title
 * - Escape closes; overlay click closes
 * - focus moves to the panel on open and returns to the trigger on close
 * - restrained panel animation (motion tokens; honours reduced motion via CSS)
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  className = ''
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children?: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
      previouslyFocused.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <div
        aria-hidden="true"
        onClick={onClose}
        className="absolute inset-0 animate-fade-in bg-slate-950/30 backdrop-blur-sm"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={clsx(
          'relative z-10 max-h-[90dvh] w-full overflow-y-auto rounded-t-xl border border-white/75 bg-white/80 shadow-high backdrop-blur-xl outline-none sm:m-4 sm:max-w-lg sm:rounded-xl animate-scale-in',
          className
        )}
      >
        <div className="flex items-start justify-between gap-4 px-5 pt-5">
          <div>
            <h2 className="text-section-heading text-text-primary">{title}</h2>
            {description ? <p className="mt-1 text-small text-text-secondary">{description}</p> : null}
          </div>
          <IconButton aria-label="Close dialog" variant="ghost" size="sm" onClick={onClose} className="-mr-2 -mt-1">
            <X />
          </IconButton>
        </div>
        <div className="px-5 py-4 text-body text-text-secondary">{children}</div>
        {footer ? (
          <div className="flex flex-wrap justify-end gap-3 border-t border-line px-5 py-4">{footer}</div>
        ) : null}
      </div>
    </div>
  );
}
