'use client';

import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import clsx from 'clsx';
import { X } from 'lucide-react';
import { BrandLogo } from '@/components/brand/brand-logo';

import { SidebarNav } from './sidebar-nav';
import { AppTopbar } from './app-topbar';

const SIDEBAR_WIDTH = '16.5rem';

/**
 * Application shell — sidebar + topbar + content.
 * Desktop (>=1024px): fixed sidebar, sticky topbar, centered content column.
 * Mobile (<1024px): hamburger in the topbar opens a navigation drawer with
 * an overlay; Escape and overlay-click close it.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? '/';
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [hash, setHash] = useState('');
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const syncHash = () => setHash(window.location.hash);
    syncHash();
    window.addEventListener('hashchange', syncHash);
    return () => window.removeEventListener('hashchange', syncHash);
  }, []);

  // Close the drawer whenever the route changes.
  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!drawerOpen) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    closeButtonRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setDrawerOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previouslyFocused.current?.focus?.();
    };
  }, [drawerOpen]);

  return (
    <div className="min-h-dvh overflow-x-hidden bg-background">
      {/* Desktop sidebar */}
      <aside
        aria-label="Sidebar"
        className="fixed inset-y-4 left-4 z-40 hidden flex-col rounded-2xl border border-white/75 bg-white/65 shadow-glass-soft backdrop-blur-glass lg:flex"
        style={{ width: SIDEBAR_WIDTH }}
      >
        <div className="flex h-16 items-center gap-2.5 border-b border-white/70 px-5">
          <BrandLogo className="h-12 w-12 shrink-0" />
          <span className="text-small font-semibold text-text-primary">ExamCraft AI</span>
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-6">
          <SidebarNav pathname={pathname} hash={hash} />
        </div>
        <div className="border-t border-white/70 px-5 py-4">
          <p className="text-metadata text-text-muted">Deterministic paper generation</p>
        </div>
      </aside>

      {/* Mobile drawer */}
      {drawerOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div
            aria-hidden="true"
            className="absolute inset-0 animate-fade-in bg-slate-950/30 backdrop-blur-sm"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="absolute inset-y-3 left-3 flex w-72 max-w-[calc(100vw-1.5rem)] animate-slide-in-left flex-col rounded-2xl border border-white/75 bg-white/80 shadow-high backdrop-blur-xl">
            <div className="flex h-16 items-center justify-between border-b border-white/70 px-4">
              <span className="flex items-center gap-2.5">
                <BrandLogo className="h-12 w-12 shrink-0" />
                <span className="text-small font-semibold text-text-primary">ExamCraft AI</span>
              </span>
              <button
                type="button"
                aria-label="Close navigation"
                ref={closeButtonRef}
                onClick={() => setDrawerOpen(false)}
                className="rounded-lg p-2 text-text-secondary transition-colors duration-micro hover:bg-white/70"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-5">
              <SidebarNav pathname={pathname} hash={hash} onNavigate={() => setDrawerOpen(false)} />
            </div>
          </div>
        </div>
      ) : null}

      {/* Main column */}
      <div className="flex min-h-dvh flex-col lg:pl-[18rem]">
        <AppTopbar pathname={pathname} onOpenNav={() => setDrawerOpen(true)} />
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </div>
  );
}
