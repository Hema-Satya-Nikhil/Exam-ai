'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { useAuth } from '@/contexts/auth-context';

export function TopBar() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  async function handleLogout() {
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
      return;
    }
    router.push('/login');
  }

  const displayName = user?.full_name?.trim() || user?.email?.split('@')[0] || 'Guest';
  const role = user?.roles?.includes('admin') ? 'Administrator' : user?.roles?.includes('faculty') ? 'Faculty' : '';

  return (
    <header className="flex items-center justify-between border-b border-white/50 bg-white/30 px-6 py-4 backdrop-blur-glass">
      <div>
        <p className="text-sm font-medium text-slate-500">Department workspace</p>
        <h2 className="text-lg font-semibold text-slate-900">ExamCraft</h2>
      </div>
      <div className="flex items-center gap-3">
        <Link href="/settings" className="rounded-full border border-white/60 bg-white/65 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-white">
          Settings
        </Link>
        {!loading && !user ? (
          <Link href="/login" className="rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800">
            Sign in
          </Link>
        ) : user ? (
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-semibold text-slate-900">{displayName}</p>
              {role ? <p className="text-xs text-slate-500">{role}</p> : null}
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
            >
              Sign out
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
