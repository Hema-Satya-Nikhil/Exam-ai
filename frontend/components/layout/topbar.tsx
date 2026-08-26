import Link from 'next/link';

export function TopBar() {
  return (
    <header className="flex items-center justify-between border-b border-white/50 bg-white/30 px-6 py-4 backdrop-blur-glass">
      <div>
        <p className="text-sm font-medium text-slate-500">Department workspace</p>
        <h2 className="text-lg font-semibold text-slate-900">ExamCraft AI</h2>
      </div>
      <div className="flex items-center gap-3">
        <Link href="/settings" className="rounded-full border border-white/60 bg-white/65 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-white">
          Settings
        </Link>
        <div className="rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700">
          System ready
        </div>
      </div>
    </header>
  );
}
