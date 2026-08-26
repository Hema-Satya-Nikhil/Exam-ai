import type { ReactNode } from 'react';

export function GlassModal({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-[2rem] border border-white/70 bg-white/75 p-6 shadow-glass backdrop-blur-glass">
      {children}
    </div>
  );
}
