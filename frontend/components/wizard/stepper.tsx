'use client';

import { Check, Circle, Lock, MinusCircle, XCircle } from 'lucide-react';

export type StepState = 'completed' | 'current' | 'optional' | 'blocked' | 'error' | 'upcoming';

export interface StepperItem {
  label: string;
  optional?: boolean;
  state: StepState;
}

const CHIP_STATES = {
  completed: 'border-success/30 bg-success-soft text-success',
  current: 'border-primary bg-primary text-white shadow-low',
  optional: 'border-warning/30 bg-warning-soft text-warning',
  error: 'border-danger/30 bg-danger-soft text-danger',
  blocked: 'border-line bg-slate-50 text-text-muted opacity-70',
  upcoming: 'border-line bg-surface text-text-muted'
} as const;

export function Stepper({ items }: { items: StepperItem[] }) {
  return (
    <nav aria-label="Paper creation steps" className="-mx-1 overflow-x-auto pb-2">
      {/* Scrollable region must be keyboard-operable (axe scrollable-region-focusable). */}
      <ol tabIndex={0} aria-label="Steps" className="flex min-w-max items-center gap-1.5 rounded-2xl border border-white/75 bg-white/55 p-3 shadow-glass-soft backdrop-blur-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary sm:gap-2 sm:p-4">
        {items.map((item, index) => (
          <li
            key={item.label + '-' + index}
            aria-current={item.state === 'current' ? 'step' : undefined}
            className="flex items-center gap-1.5 sm:gap-2"
          >
            {index > 0 ? <span className="h-px w-3 bg-slate-200 sm:w-5" aria-hidden /> : null}
            <div
              className={
                'flex items-center gap-2 rounded-pill border px-2.5 py-1.5 text-metadata font-medium transition-colors duration-micro ease-standard sm:px-4 sm:py-2 sm:text-small ' +
                CHIP_STATES[item.state]
              }
            >
              <StepIcon state={item.state} />
              <span>{item.label}</span>
              {item.optional ? (
                <span className="rounded-pill border border-current px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide sm:text-[11px]">
                  Optional
                </span>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
    </nav>
  );
}

function StepIcon({ state }: { state: StepState }) {
  switch (state) {
    case 'completed':
      return <Check className="h-3.5 w-3.5 sm:h-4 sm:w-4" data-testid="step-completed" aria-hidden />;
    case 'current':
      return <Circle className="h-3.5 w-3.5 fill-white text-white sm:h-4 sm:w-4" data-testid="step-current" aria-hidden />;
    case 'optional':
      return <MinusCircle className="h-3.5 w-3.5 sm:h-4 sm:w-4" data-testid="step-optional" aria-hidden />;
    case 'error':
      return <XCircle className="h-3.5 w-3.5 sm:h-4 sm:w-4" data-testid="step-error" aria-hidden />;
    case 'blocked':
      return <Lock className="h-3.5 w-3.5 sm:h-4 sm:w-4" data-testid="step-blocked" aria-hidden />;
    default:
      return <Circle className="h-3.5 w-3.5 text-text-muted sm:h-4 sm:w-4" data-testid="step-pending" aria-hidden />;
  }
}
