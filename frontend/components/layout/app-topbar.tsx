'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { ChevronDown, LogOut, Menu, Moon, Settings, Sun, UserCircle2 } from 'lucide-react';

import { useAuth } from '@/contexts/auth-context';
import { getPageContext } from './nav-items';
import { useTheme } from '@/contexts/theme-context';
import { BrandLogo } from '@/components/brand/brand-logo';

/**
 * Topbar — mobile menu button, wordmark, current page context, user identity
 * and profile menu (Account / Settings / Sign out). Sticky, never overlaps.
 */
export function AppTopbar({ pathname, onOpenNav }: { pathname: string; onOpenNav: () => void }) {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onDocClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  const displayName = user?.full_name?.trim() || user?.email?.split('@')[0] || 'Guest';
  const role = user?.roles?.includes('admin') ? 'Administrator' : user?.roles?.includes('faculty') ? 'Faculty' : '';

  async function handleSignOut() {
    setMenuOpen(false);
    try {
      await logout();
    } catch {
      // tokens are cleared regardless
    }
    router.push('/login');
  }

  return (
    <header className="sticky top-3 z-30 mx-3 flex h-14 items-center justify-between gap-4 rounded-xl border border-white/75 bg-white/65 px-4 shadow-glass-soft backdrop-blur-glass transition-all sm:mx-6 sm:px-6 lg:ml-4 lg:mr-8">
      <div className="flex min-w-0 items-center gap-2 sm:gap-3">
        <button
          type="button"
          onClick={onOpenNav}
          aria-label="Open navigation"
          aria-haspopup="dialog"
          className="-ml-1 rounded-lg p-2 text-text-secondary transition-colors duration-micro hover:bg-white/70 lg:hidden"
        >
          <Menu className="h-5 w-5" aria-hidden="true" />
        </button>
        <BrandLogo className="h-11 w-11 shrink-0" />
        <div className="min-w-0 leading-tight">
          <p className="truncate text-small font-semibold text-text-primary">ExamCraft AI</p>
          <p className="truncate text-metadata text-text-muted">{getPageContext(pathname)}</p>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
          className="rounded-lg p-2 text-text-secondary transition-colors duration-micro hover:bg-white/70 dark:hover:bg-slate-800/70"
        >
          {theme === 'light' ? <Moon className="h-4 w-4" aria-hidden="true" /> : <Sun className="h-4 w-4" aria-hidden="true" />}
        </button>
      <div className="relative shrink-0" ref={menuRef}>
        <button
          type="button"
          onClick={() => setMenuOpen((v) => !v)}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-label="Profile menu"
          className="flex items-center gap-2 rounded-lg py-1.5 pl-2 pr-1.5 transition-colors duration-micro ease-standard hover:bg-white/70"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-pill bg-primary-soft text-primary" aria-hidden="true">
            <UserCircle2 className="h-5 w-5" />
          </span>
          <span className="hidden min-w-0 text-left leading-tight sm:block">
            <span className="block max-w-[160px] truncate text-small font-medium text-text-primary">{displayName}</span>
            {role ? <span className="block text-metadata text-text-muted">{role}</span> : null}
          </span>
          <ChevronDown aria-hidden="true" className={`h-4 w-4 text-text-muted transition-transform duration-micro ${menuOpen ? 'rotate-180' : ''}`} />
        </button>

        {menuOpen ? (
          <div
            role="menu"
            aria-label="Profile"
            className="absolute right-0 top-[calc(100%+6px)] w-52 animate-scale-in rounded-xl border border-white/75 bg-white/85 py-1.5 shadow-high backdrop-blur-xl"
          >
            <div className="border-b border-white/70 px-3 pb-2 pt-1 sm:hidden">
              <p className="truncate text-small font-medium text-text-primary">{displayName}</p>
              {role ? <p className="text-metadata text-text-muted">{role}</p> : null}
            </div>
            <Link
              href="/settings"
              role="menuitem"
              onClick={() => setMenuOpen(false)}
              className="flex items-center gap-2.5 px-3 py-2 text-small text-text-secondary transition-colors duration-micro hover:bg-white/70 hover:text-text-primary"
            >
              <UserCircle2 className="h-4 w-4 text-text-muted" aria-hidden="true" />
              Account
            </Link>
            <Link
              href="/settings"
              role="menuitem"
              onClick={() => setMenuOpen(false)}
              className="flex items-center gap-2.5 px-3 py-2 text-small text-text-secondary transition-colors duration-micro hover:bg-white/70 hover:text-text-primary"
            >
              <Settings className="h-4 w-4 text-text-muted" aria-hidden="true" />
              Settings
            </Link>
            <button
              type="button"
              role="menuitem"
              onClick={handleSignOut}
              className="flex w-full items-center gap-2.5 border-t border-white/70 px-3 py-2 text-left text-small text-danger transition-colors duration-micro hover:bg-danger-soft"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Sign out
            </button>
          </div>
        ) : null}
      </div>
      </div>
    </header>
  );
}
