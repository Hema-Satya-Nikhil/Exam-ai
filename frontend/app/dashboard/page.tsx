import Link from 'next/link';

import { GlassCard } from '@/components/ui/glass-card';
import { TopBar } from '@/components/layout/topbar';

export default function DashboardPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.9),_rgba(226,232,240,0.6)_34%,_rgba(203,213,225,0.25)_70%,_rgba(15,23,42,0.04))]">
      <TopBar />
      <section className="mx-auto grid max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[1.4fr_0.6fr]">
        <GlassCard>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-950">Create Your Question Paper</h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
            Configure the syllabus, paper structure, question distribution, and evaluation criteria before generation.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/create" className="inline-flex rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800">
              Create a new paper
            </Link>
            <Link href="/review" className="inline-flex rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100">
              Open review workspace
            </Link>
          </div>
        </GlassCard>
        <GlassCard>
          <p className="text-sm font-medium text-slate-500">Paper-creation workflow</p>
          <div className="mt-4 space-y-3 text-sm text-slate-700">
            <div>1. Subject and exam setup</div>
            <div>2. Syllabus — upload and confirm</div>
            <div>3. Optional unit materials</div>
            <div>4. Paper pattern and question structure</div>
            <div>5. Blueprint and evaluation levels</div>
            <div>6. Generate, review, approve, export</div>
          </div>
        </GlassCard>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 pb-10 lg:grid-cols-[1.15fr_0.85fr]">
        <GlassCard>
          <p className="text-sm font-medium text-slate-500">Recent papers</p>
          <div className="mt-4 rounded-3xl border border-dashed border-slate-300 bg-white/60 p-8 text-center">
            <p className="text-sm font-medium text-slate-700">No papers yet</p>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Generated papers will appear here for review, approval, and export.
            </p>
            <Link href="/create" className="mt-5 inline-flex rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800">
              Create the first paper
            </Link>
          </div>
        </GlassCard>

        <GlassCard>
          <p className="text-sm font-medium text-slate-500">Before you start</p>
          <div className="mt-4 space-y-3 text-sm leading-6 text-slate-600">
            <p>• Your syllabus file defines the units and topics used as sources.</p>
            <p>• The paper structure must add up to the total marks before generation.</p>
            <p>• Every paper is reviewed and approved by you before it can be exported.</p>
          </div>
        </GlassCard>
      </section>
    </main>
  );
}
