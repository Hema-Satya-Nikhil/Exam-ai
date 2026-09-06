'use client';

import clsx from 'clsx';
import { useId } from 'react';
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes
} from 'react';

/* ---------------------------------------------------------------
   Shared field primitives. Every control renders an accessible
   label, an error slot with aria wiring, and a visible focus ring.
   --------------------------------------------------------------- */

const CONTROL_BASE =
  'w-full rounded-lg border bg-white/70 px-3 text-body text-text-primary shadow-inner placeholder:text-text-muted backdrop-blur-sm transition-all duration-micro ease-standard disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-text-muted';

const CONTROL_STATE = {
  normal: 'border-white/80 hover:border-slate-300 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20',
  error: 'border-danger focus:border-danger focus:outline-none focus:ring-2 focus:ring-danger/20'
} as const;

export interface FieldProps {
  label: string;
  /** Optional hint rendered between the label and the control. */
  hint?: string;
  /** Validation message; switches the control into the error state. */
  error?: string;
  /** Render-prop receives the generated ids for aria wiring. */
  children: (ids: { id: string; describedBy?: string; invalid: boolean }) => ReactNode;
  className?: string;
  /** Hide the visual label while keeping it for screen readers. */
  hideLabel?: boolean;
}

/** Structured field wrapper — label + control + error, fully wired. */
export function Field({ label, hint, error, children, className = '', hideLabel = false }: FieldProps) {
  const id = useId();
  const errorId = error ? `${id}-error` : undefined;
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className={clsx('flex flex-col gap-1.5', className)}>
      <label htmlFor={id} className={clsx('text-label text-text-secondary', hideLabel && 'sr-only')}>
        {label}
      </label>
      {hint ? (
        <p id={hintId} className="text-metadata text-text-muted">
          {hint}
        </p>
      ) : null}
      {children({ id, describedBy: errorId ?? hintId, invalid: Boolean(error) })}
      {error ? (
        <p id={errorId} role="alert" className="text-metadata font-medium text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'aria-describedby' | 'aria-invalid'> {
  id: string;
  describedBy?: string;
  invalid?: boolean;
}

export function Input({ className = '', invalid = false, describedBy, ...rest }: InputProps) {
  return (
    <input
      {...rest}
      id={rest.id}
      aria-invalid={invalid || undefined}
      aria-describedby={describedBy}
      className={clsx('h-10', CONTROL_BASE, invalid ? CONTROL_STATE.error : CONTROL_STATE.normal, className)}
    />
  );
}

export interface TextareaProps extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id' | 'aria-describedby' | 'aria-invalid'> {
  id: string;
  describedBy?: string;
  invalid?: boolean;
}

export function Textarea({ className = '', rows = 4, invalid = false, describedBy, ...rest }: TextareaProps) {
  return (
    <textarea
      {...rest}
      rows={rows}
      id={rest.id}
      aria-invalid={invalid || undefined}
      aria-describedby={describedBy}
      className={clsx('py-2.5', CONTROL_BASE, invalid ? CONTROL_STATE.error : CONTROL_STATE.normal, className)}
    />
  );
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id' | 'aria-describedby' | 'aria-invalid'> {
  id: string;
  describedBy?: string;
  invalid?: boolean;
  children: ReactNode;
}

const CHEVRON_BG =
  'bg-[url("data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2364748b%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22m6%209%206%206%206-6%22%2F%3E%3C%2Fsvg%3E")] bg-[position:right_0.75rem_center] bg-no-repeat';

export function Select({ className = '', children, invalid = false, describedBy, ...rest }: SelectProps) {
  return (
    <select
      {...rest}
      id={rest.id}
      aria-invalid={invalid || undefined}
      aria-describedby={describedBy}
      className={clsx('h-10 appearance-none pr-9', CHEVRON_BG, CONTROL_BASE, invalid ? CONTROL_STATE.error : CONTROL_STATE.normal, className)}
    >
      {children}
    </select>
  );
}

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'type'> {
  id: string;
  label: string;
}

export function Checkbox({ id, label, className = '', ...rest }: CheckboxProps) {
  return (
    <div className={clsx('flex items-center gap-2', className)}>
      <input
        {...rest}
        type="checkbox"
        id={id}
        className="h-4 w-4 rounded-sm border-line accent-[rgb(var(--primary))] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50"
      />
      <label htmlFor={id} className="text-small text-text-secondary select-none">
        {label}
      </label>
    </div>
  );
}

export interface RadioProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'type'> {
  id: string;
  label: string;
}

export function Radio({ id, label, className = '', ...rest }: RadioProps) {
  return (
    <div className={clsx('flex items-center gap-2', className)}>
      <input
        {...rest}
        type="radio"
        id={id}
        className="h-4 w-4 border-line accent-[rgb(var(--primary))] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50"
      />
      <label htmlFor={id} className="text-small text-text-secondary select-none">
        {label}
      </label>
    </div>
  );
}

export interface SwitchProps {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
}

/** Accessible toggle — button with role="switch" (keyboard operable). */
export function Switch({ id, label, checked, onChange, disabled = false, className = '' }: SwitchProps) {
  return (
    <div className={clsx('flex items-center gap-2.5', className)}>
      <button
        type="button"
        role="switch"
        id={id}
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={clsx(
          'relative inline-flex h-5 w-9 shrink-0 items-center rounded-pill border transition-colors duration-micro ease-standard focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50',
          checked ? 'border-primary bg-primary' : 'border-line bg-slate-200'
        )}
      >
        <span
          aria-hidden="true"
          className={clsx(
            'inline-block h-3.5 w-3.5 transform rounded-pill bg-white shadow-low transition-transform duration-micro ease-standard',
            checked ? 'translate-x-[1.15rem]' : 'translate-x-0.5'
          )}
        />
      </button>
      <label htmlFor={id} className="text-small text-text-secondary select-none">
        {label}
      </label>
    </div>
  );
}
