import clsx from 'clsx';

/** Indeterminate activity spinner. Pure CSS — no animation loop in JS.
 *  Decorative inside labelled controls (e.g. Button sets aria-busy itself). */
export function Spinner({ className = '', label }: { className?: string; label?: string }) {
  return (
    <span
      {...(label ? { role: 'status', 'aria-label': label } : { 'aria-hidden': true })}
      className={clsx('inline-flex', className)}
    >
      <svg
        className="h-4 w-4 animate-spin text-current"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path
          className="opacity-90"
          fill="currentColor"
          d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z"
        />
      </svg>
    </span>
  );
}
