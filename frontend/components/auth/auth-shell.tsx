import type { ReactNode } from 'react';
import { Moon, Sun } from 'lucide-react';

import { GlassPanel } from '@/components/ui/glass-surface';
import { useTheme } from '@/contexts/theme-context';
import { BrandLogo } from '@/components/brand/brand-logo';

export function AuthShell({ children }: { children: ReactNode }) {
  const { theme, toggleTheme } = useTheme();
  return (
    <main className="public-ambient relative flex min-h-screen items-start justify-center overflow-x-hidden overflow-y-auto bg-background px-4 py-8 text-text-primary sm:px-6 sm:py-12">
      <button
        type="button"
        onClick={toggleTheme}
        aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
        className="public-control absolute right-4 top-4 z-20 rounded-xl p-2 text-text-secondary transition-colors hover:border-primary/50 hover:text-primary sm:right-6 sm:top-6"
      >
        {theme === 'light' ? <Moon className="h-4 w-4" aria-hidden="true" /> : <Sun className="h-4 w-4" aria-hidden="true" />}
      </button>
      <div aria-hidden="true" className="pointer-events-none absolute -left-24 top-[-8rem] h-72 w-72 rounded-full bg-primary-soft/30 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute -right-24 bottom-[-8rem] h-80 w-80 rounded-full bg-info-soft/30 blur-3xl" />
      <div className="relative z-10 my-4 w-full max-w-md animate-fade-in sm:my-8">
        <div className="mb-3 flex justify-center">
          <BrandLogo className="h-28 w-28 sm:h-32 sm:w-32" priority />
        </div>
        {children}
      </div>
    </main>
  );
}

export function AuthPanel({ children }: { children: ReactNode }) {
  return <GlassPanel className="public-glass w-full p-6 shadow-glass sm:p-8">{children}</GlassPanel>;
}

export function AuthSteps({ current }: { current: 1 | 2 | 3 }) {
  const steps = ['Email', 'Verify', 'Reset'];
  return (
    <ol aria-label="Password reset progress" className="mb-7 flex items-center">
      {steps.map((step, index) => {
        const number = index + 1;
        const active = number === current;
        const complete = number < current;
        return (
          <li key={step} className="flex flex-1 items-center last:flex-none">
            <div className="flex items-center gap-2">
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full text-metadata font-semibold transition-colors ${
                  active || complete ? 'bg-primary text-white shadow-low' : 'border border-line bg-surface/60 text-text-muted'
                }`}
              >
                {number}
              </span>
              <span className={`hidden text-metadata sm:inline ${active ? 'font-semibold text-text-primary' : 'text-text-muted'}`}>
                {step}
              </span>
            </div>
            {number < steps.length ? <span className={`mx-2 h-px flex-1 ${complete ? 'bg-primary/50' : 'bg-line'}`} /> : null}
          </li>
        );
      })}
    </ol>
  );
}