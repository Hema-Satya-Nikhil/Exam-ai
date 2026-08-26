import Link from 'next/link';

import { GlassCard } from '@/components/ui/glass-card';
import { TopBar } from '@/components/layout/topbar';

const reservedFields = [
  {
    label: 'NVIDIA API key',
    value: 'Paste your key here when provider access is ready.',
    helper: 'Stored server-side later. Do not commit the real secret to source control.'
  },
  {
    label: 'NVIDIA model',
    value: 'nim/meta/llama-3.1-70b-instruct',
    helper: 'Default generation model used by the backend.'
  },
  {
    label: 'MongoDB URI',
    value: 'mongodb://localhost:27017',
    helper: 'Reserved for document/session storage wiring.'
  },
  {
    label: 'MongoDB database',
    value: 'examcraft_ai',
    helper: 'Database name for persisted records and workflow artifacts.'
  }
];

export default function SettingsPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.95),_rgba(226,232,240,0.72)_30%,_rgba(203,213,225,0.28)_62%,_rgba(15,23,42,0.05))] text-slate-900">
      <TopBar />
      <section className="mx-auto grid max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[1.15fr_0.85fr]">
        <GlassCard>
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-slate-500">System settings</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950">Reserved configuration slots for model and database access.</h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
            This screen keeps the backend integration points visible so you can paste the real NVIDIA and MongoDB values when the deployment is ready.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/dashboard" className="inline-flex rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800">
              Back to dashboard
            </Link>
            <Link href="/create" className="inline-flex rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100">
              Open wizard
            </Link>
          </div>
        </GlassCard>

        <GlassCard>
          <p className="text-sm font-medium text-slate-500">Deployment note</p>
          <div className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
            <p>The current app keeps these values as placeholders rather than persisting secrets in the UI.</p>
            <p>When backend settings storage is connected, this page can become the control surface for runtime environment values.</p>
          </div>
        </GlassCard>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 pb-10 lg:grid-cols-2">
        {reservedFields.map((field) => (
          <GlassCard key={field.label}>
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-slate-500">{field.label}</p>
            <div className="mt-4 rounded-3xl border border-slate-200/70 bg-white/80 p-4 shadow-sm">
              <div className="text-sm font-medium text-slate-500">Current placeholder</div>
              <div className="mt-2 text-lg font-semibold text-slate-950">{field.value}</div>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600">{field.helper}</p>
          </GlassCard>
        ))}
      </section>
    </main>
  );
}
