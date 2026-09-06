'use client';

import Link from 'next/link';
import type { Route } from 'next';
import clsx from 'clsx';

import { NAV_GROUPS, type NavGroup, type NavItem } from './nav-items';
import { useAuth } from '@/contexts/auth-context';

function isItemVisible(item: NavItem, isAdmin: boolean): boolean {
  return item.requiresRole !== 'admin' || isAdmin;
}

/**
 * Sidebar navigation (desktop) and drawer content (mobile).
 * Active route: exact path match; hash/qualifier links only highlight
 * when their specific destination is current.
 */
export function SidebarNav({
  pathname,
  hash = '',
  onNavigate
}: {
  pathname: string;
  /** e.g. '#recent' — used for anchor destinations like /dashboard#recent. */
  hash?: string;
  onNavigate?: () => void;
}) {
  const { user } = useAuth();
  const isAdmin = !!user?.roles?.includes('admin');

  return (
    <nav aria-label="Primary" className="flex flex-col gap-7">
      {NAV_GROUPS.map((group: NavGroup) => {
        const items = group.items.filter((i) => isItemVisible(i, isAdmin));
        if (items.length === 0) return null;
        return (
          <div key={group.title}>
            <p className="px-3 pb-2 text-metadata font-semibold uppercase tracking-[0.16em] text-text-muted">
              {group.title}
            </p>
            <ul className="flex flex-col gap-0.5">
              {items.map((item) => {
                const [basePath, qualifier] = item.href.split(/[#?]/);
                const hasQualifier = Boolean(item.href.match(/[#?]/));
                const active = hasQualifier
                  ? pathname === basePath && `#${item.href.split('#')[1] ?? ''}` === hash
                  : pathname === basePath || pathname.startsWith(`${basePath}/`);

                return (
                  <li key={item.href}>
                    <Link
                      href={item.href as Route}
                      onClick={onNavigate}
                      aria-current={active ? 'page' : undefined}
                      className={clsx(
                        'group relative flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-small font-medium transition-all duration-micro ease-standard focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
                        active
                          ? 'bg-primary-soft/75 text-primary shadow-low'
                          : 'text-text-secondary hover:bg-white/65 hover:text-text-primary'
                      )}
                    >
                      {active ? <span aria-hidden="true" className="absolute left-0 h-5 w-0.5 rounded-full bg-primary" /> : null}
                      <item.icon
                        aria-hidden="true"
                        className={clsx('h-[18px] w-[18px] shrink-0', active ? 'text-primary' : 'text-text-muted group-hover:text-text-secondary')}
                      />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}
