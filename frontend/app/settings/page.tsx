import Link from 'next/link';

import { GlassCard } from '@/components/ui/glass-card';
import { TopBar } from '@/components/layout/topbar';

export default function SettingsPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.95),_rgba(226,232,240,0.72)_30%,_rgba(203,213,225,0.28)_62%,_rgba(15,23,42,0.05))] text-slate-900">
      <TopBar />
      <section className="mx-auto grid max-w-4xl gap-6 px-6 py-8">
        <GlassCard>
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-slate-500">Settings</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">Department workspace</h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
            Your account is used to attribute every generated paper, approval, and export. Environment configuration is managed by the department and kept out of the browser.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/dashboard" className="inline-flex rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800">
              Back to dashboard
            </Link>
            <Link href="/create" className="inline-flex rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100">
              Create a paper
            </Link>
          </div>
        </GlassCard>
      </section>
    </main>
  );
}
