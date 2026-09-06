"use client";

import Link from 'next/link';
import { Mail } from 'lucide-react';

import { useAuth } from '@/contexts/auth-context';
import { BrandLogo } from '@/components/brand/brand-logo';

/**
 * Minimal landing footer. Authentication-aware: signed-out visitors see
 * Login / Create account; signed-in users see their workspace shortcuts.
 * Auth state comes from the existing context — no new API calls beyond the
 * session restore the provider already performs.
 */
export function LandingFooter() {
  const { user } = useAuth();
  const linkClass =
    'text-small text-text-secondary transition-colors duration-micro hover:text-primary';

  return (
    <footer className="border-t border-line bg-surface/60">
      <div className="mx-auto grid max-w-7xl gap-8 px-6 py-10 sm:grid-cols-[auto_1fr_auto] sm:items-center lg:px-10">
        <div className="flex items-center gap-3">
          <BrandLogo className="h-16 w-16 shrink-0" />
          <div>
            <p className="text-label font-semibold tracking-tight text-text-primary">ExamCraft AI</p>
            <p className="mt-1 text-metadata text-text-muted">Created by Hema Satya Nikhil</p>
          </div>
        </div>
        <nav aria-label="Footer" className="flex flex-wrap items-center gap-x-6 gap-y-2 sm:justify-center">
          <Link href="/" className={linkClass}>Home</Link>
          {user ? (
            <>
              <Link href="/create" className={linkClass}>
                Create Paper
              </Link>
              <Link href="/dashboard" className={linkClass}>
                Dashboard
              </Link>
              <Link href="/settings" className={linkClass}>
                Settings
              </Link>
            </>
          ) : (
            <>
              <Link href="/login" className={linkClass}>
                Login
              </Link>
              <Link href="/login" className={linkClass}>
                Create account
              </Link>
            </>
          )}
          <a href="mailto:hemasatyanikhil@gmail.com" className={`${linkClass} inline-flex items-center gap-1.5`}>
            <Mail className="h-3.5 w-3.5" aria-hidden="true" />
            Contact
          </a>
        </nav>
        <p className="text-small text-text-secondary sm:text-right">
          <a href="mailto:hemasatyanikhil@gmail.com" className="transition-colors hover:text-primary">
            hemasatyanikhil@gmail.com
          </a>
        </p>
      </div>
    </footer>
  );
}
