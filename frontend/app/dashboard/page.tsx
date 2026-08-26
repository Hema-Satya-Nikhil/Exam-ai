import Link from 'next/link';

import { GlassCard } from '@/components/ui/glass-card';
import { TopBar } from '@/components/layout/topbar';

export default function DashboardPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.9),_rgba(226,232,240,0.6)_34%,_rgba(203,213,225,0.25)_70%,_rgba(15,23,42,0.04))]">
      <TopBar />
      <section className="mx-auto grid max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[1.4fr_0.6fr]">
        <GlassCard>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-950">Create and validate question papers from a governed blueprint.</h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
            The backend controls academic rules, versioning, and validation. The LLM only fills in constrained question wording.
          </p>
          <div className="mt-6">
            <Link href="/create" className="inline-flex rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800">
              Open creation wizard
            </Link>
            <Link href="/review" className="ml-3 inline-flex rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100">
              Open review workspace
            </Link>
          </div>
        </GlassCard>
        <GlassCard>
          <p className="text-sm font-medium text-slate-500">Workflow</p>
          <div className="mt-4 space-y-3 text-sm text-slate-700">
            <div>1. Subject and exam setup</div>
            <div>2. Syllabus and unit material ingestion</div>
            <div>3. Blueprint review and generation</div>
            <div>4. Faculty approval and export</div>
          </div>
        </GlassCard>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 pb-10 lg:grid-cols-[1.15fr_0.85fr]">
        <GlassCard>
          <p className="text-sm font-medium text-slate-500">Recent papers</p>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <RecentPaperCard title="Mid 2 - Data Mining" status="Under review" accent="emerald" />
            <RecentPaperCard title="Mid 1 - Database Systems" status="Draft" accent="amber" />
            <RecentPaperCard title="End Semester - AI" status="Approved" accent="blue" />
          </div>
        </GlassCard>

        <GlassCard>
          <p className="text-sm font-medium text-slate-500">System status</p>
          <div className="mt-4 space-y-3 text-sm text-slate-700">
            <StatusRow label="Blueprint validation" value="Ready" />
            <StatusRow label="NVIDIA key" value="Backend only" />
            <StatusRow label="Export pipeline" value="Enabled" />
            <StatusRow label="Review workspace" value="Available" />
          </div>
          <div className="mt-6 rounded-3xl border border-slate-200/70 bg-white/70 p-4">
            <p className="text-sm font-medium text-slate-500">Configuration</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Keep provider and database placeholders in one place while the backend persistence layer is being completed.
            </p>
            <Link href="/settings" className="mt-4 inline-flex rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800">
              Open settings
            </Link>
          </div>
        </GlassCard>
      </section>
    </main>
  );
}

function RecentPaperCard({ title, status, accent }: { title: string; status: string; accent: 'emerald' | 'amber' | 'blue' }) {
  const colors = {
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
    blue: 'border-sky-200 bg-sky-50 text-sky-700'
  } as const;

  return (
    <div className="rounded-3xl border border-white/70 bg-white/70 p-4 shadow-sm backdrop-blur-glass">
      <div className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium ${colors[accent]}`}>{status}</div>
      <h3 className="mt-4 text-lg font-semibold text-slate-950">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-600">Open the review workspace to edit, lock, regenerate, or export this paper.</p>
    </div>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-white/70 bg-white/70 px-4 py-3">
      <span>{label}</span>
      <span className="font-medium text-slate-950">{value}</span>
    </div>
  );
}
