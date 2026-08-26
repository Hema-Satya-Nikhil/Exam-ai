import Link from 'next/link';
import { ArrowRight, FileText, ShieldCheck, Sparkles } from 'lucide-react';

const highlights = [
  {
    title: 'Deterministic blueprint control',
    description: 'Academic rules stay in the backend, while the model only generates controlled wording.'
  },
  {
    title: 'Versioned faculty workflow',
    description: 'Every syllabus, blueprint, validation result, and approval step is tracked.'
  },
  {
    title: 'Liquid glass review surface',
    description: 'A premium, low-noise interface built for actual departmental use.'
  }
];

export default function HomePage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.95),_rgba(226,232,240,0.72)_30%,_rgba(203,213,225,0.28)_62%,_rgba(15,23,42,0.05))] text-slate-900">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-80 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.18),_transparent_58%),radial-gradient(circle_at_top_right,_rgba(15,23,42,0.08),_transparent_42%)]" />
      <div className="pointer-events-none absolute left-10 top-28 h-24 w-24 rounded-full bg-sky-300/20 blur-3xl" />
      <div className="pointer-events-none absolute right-16 top-56 h-32 w-32 rounded-full bg-slate-300/25 blur-3xl" />
      <section className="mx-auto flex min-h-screen max-w-7xl flex-col justify-center px-6 py-16 lg:px-10">
        <div className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
          <div className="space-y-8">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/60 bg-white/60 px-4 py-2 text-sm font-medium text-slate-700 shadow-glass backdrop-blur-glass">
              <Sparkles className="h-4 w-4 text-slate-500" />
              ExamCraft AI
            </div>
            <div className="space-y-5">
              <h1 className="max-w-3xl text-5xl font-semibold tracking-tight text-slate-950 md:text-7xl">
                Exam papers with governed generation and clean faculty review.
              </h1>
              <p className="max-w-2xl text-lg leading-8 text-slate-600 md:text-xl">
                Faculty define the blueprint, the backend enforces the academic rules, and NVIDIA generates only constrained question text.
              </p>
            </div>
            <div className="flex flex-wrap gap-4">
              <Link href="/create" className="glass-button group inline-flex items-center gap-2 rounded-full bg-slate-950 px-6 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-slate-800">
                Start a draft
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <Link href="/dashboard" className="glass-button inline-flex items-center gap-2 rounded-full border border-white/60 bg-white/55 px-6 py-3 text-sm font-semibold text-slate-800 backdrop-blur-glass transition hover:-translate-y-0.5 hover:bg-white/70">
                Review workspace
              </Link>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <MetricPill label="Blueprints" value="Validated" />
              <MetricPill label="LLM output" value="Constrained" />
              <MetricPill label="Review flow" value="Versioned" />
            </div>
          </div>

          <div className="glass-panel space-y-4 rounded-[2rem] border border-white/60 bg-white/60 p-5 shadow-glass backdrop-blur-glass">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-500">System status</p>
                <h2 className="mt-1 text-xl font-semibold text-slate-900">Ready for faculty workflows</h2>
              </div>
              <ShieldCheck className="h-6 w-6 text-emerald-600" />
            </div>
            <div className="rounded-3xl border border-slate-200/70 bg-slate-950 px-4 py-4 text-white shadow-lg shadow-slate-950/20">
              <div className="flex items-center gap-3 text-sm font-medium text-slate-300">
                <FileText className="h-4 w-4" />
                Blueprint validation pipeline
              </div>
              <div className="mt-4 grid gap-3 text-sm">
                <div className="rounded-2xl bg-white/10 px-4 py-3">Structure validation</div>
                <div className="rounded-2xl bg-white/10 px-4 py-3">Unit scope verification</div>
                <div className="rounded-2xl bg-white/10 px-4 py-3">Bloom and duplication checks</div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-14 grid gap-4 md:grid-cols-3">
          {highlights.map((item) => (
            <article key={item.title} className="glass-panel rounded-[1.75rem] border border-white/60 bg-white/50 p-6 shadow-glass backdrop-blur-glass">
              <h3 className="text-lg font-semibold text-slate-900">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">{item.description}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-3xl border border-white/60 bg-white/55 px-4 py-3 shadow-glass backdrop-blur-glass">
      <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}
