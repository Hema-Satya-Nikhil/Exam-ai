import { SeparatorHorizontal } from 'lucide-react';

/**
 * Reusable "OR" divider used between choice-group alternatives in Part B.
 * Renders a prominent, accessible horizontal rule with a centered "OR" label
 * so the alternative relationship is visually obvious — not a tiny badge.
 */
export function OrDivider() {
  return (
    <div
      role="separator"
      aria-label="OR"
      data-testid="or-divider"
      className="relative my-5 flex items-center"
    >
      <span className="absolute inset-0 flex items-center">
        <span className="h-px w-full border-t border-line" />
      </span>
      <span
        data-testid="or-label"
        className="relative inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary-soft px-4 py-1 text-small font-extrabold uppercase tracking-[0.3em] text-primary"
      >
        <SeparatorHorizontal className="h-4 w-4" aria-hidden="true" />
        OR
      </span>
    </div>
  );
}
