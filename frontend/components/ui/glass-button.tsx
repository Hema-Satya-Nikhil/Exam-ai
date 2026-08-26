import type { ButtonHTMLAttributes, ReactNode } from 'react';

export function GlassButton({ children, className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center rounded-full px-6 py-3 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-slate-900/20 ${className}`}
    >
      {children}
    </button>
  );
}
