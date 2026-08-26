import type { ReactNode } from 'react';

export function GlassCard({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-[2rem] border border-white/60 bg-white/55 p-6 shadow-glass backdrop-blur-glass">
      {children}
    </div>
  );
}
