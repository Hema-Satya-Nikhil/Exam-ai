const fs = require('fs');
const P = 'components/review/paper-review.tsx';
let t = fs.readFileSync(P, 'utf8').replace(/\r\n/g, '\n');
let misses = [];
function rep(from, to) {
  const n = t.split(from).length - 1;
  if (n === 0) { misses.push(from.slice(0, 70).replace(/\n/g, ' ')); return; }
  t = t.split(from).join(to);
}

// --- header: subtitle + status badge + Back to Dashboard ---
rep(
  '        <div className="flex flex-wrap items-center justify-between gap-3">\n          <div>\n            <p className="text-sm font-medium text-slate-500">Review Question Paper</p>\n            <h1 className="text-2xl font-semibold tracking-tight text-slate-950">{draft?.title || \'Question paper\'}</h1>\n          </div>\n          <Link href="/dashboard" className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100">\n            <ArrowLeft className="h-4 w-4" /> Dashboard\n          </Link>\n        </div>',
  '        <div className="flex flex-wrap items-center justify-between gap-3">\n          <div>\n            <p className="text-metadata font-semibold uppercase tracking-[0.14em] text-text-muted">Review Question Paper</p>\n            <h1 className="text-heading tracking-tight text-text-primary">{draft?.title || \'Question paper\'}</h1>\n            <p className="mt-1 text-small text-text-secondary">Review, refine, and export your examination paper.</p>\n          </div>\n          <div className="flex flex-wrap items-center gap-3">\n            {draft && !isLoading && !isError ? (\n              <span data-testid="review-status" className="inline-flex items-center">\n                <Badge tone={finalCheckPassed ? \'success\' : \'danger\'}>{finalCheckPassed ? \'Valid\' : \'Needs attention\'}</Badge>\n              </span>\n            ) : null}\n            <Link href="/dashboard" className="inline-flex items-center gap-2 rounded-[0.5rem] border border-line bg-surface px-4 py-2 text-small font-semibold text-text-secondary transition-colors duration-micro ease-standard hover:bg-slate-50">\n              <ArrowLeft className="h-4 w-4" /> Back to Dashboard\n            </Link>\n          </div>\n        </div>'
);

// --- not-found branch -> Unable to load + Retry ---
rep(
  '          <div className="mt-8 rounded-[2rem] border border-red-200 bg-red-50 p-10 text-center">\n            <h2 className="text-lg font-semibold text-red-800">Paper not found</h2>\n            <p className="mt-2 text-sm text-red-700">We could not load this paper. It may have been created in a different session.</p>\n            <Link href="/create" className="mt-5 inline-flex rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800">\n              Create a new paper\n            </Link>\n          </div>',
  '          <div className="mt-8 rounded-lg border border-danger/25 bg-danger-soft p-10 text-center">\n            <h2 className="text-body font-semibold text-danger">Unable to load this question paper.</h2>\n            <p className="mt-2 text-small text-danger">It may have been created in a different session. Please try again.</p>\n            <button\n              type="button"\n              onClick={() => { if (typeof window !== \'undefined\') window.location.reload(); }}\n              className="mt-5 inline-flex rounded-[0.5rem] bg-primary px-5 py-2.5 text-small font-semibold text-white transition-colors duration-micro hover:bg-primary-hover"\n            >\n              Retry\n            </button>\n            <Link href="/create" className="mt-3 block text-small font-medium text-primary hover:underline">Create a new paper</Link>\n          </div>'
);

// --- isLoading branch -> skeleton card ---
rep(
  '          <div className="mt-8 flex items-center justify-center gap-3 rounded-[2rem] border border-white/60 bg-white/60 p-10 text-slate-600">\n            <Loader2 className="h-5 w-5 animate-spin" /> Loading paper…\n          </div>',
  '          <div className="mt-8 rounded-lg border border-line bg-surface p-8 shadow-low">\n            <div className="space-y-3">\n              <Skeleton className="h-7 w-64" />\n              <Skeleton className="h-24 w-full" />\n              <Skeleton className="h-24 w-full" />\n            </div>\n          </div>'
);

// --- no-paper + sign-in branch cosmetic classes ---
rep('rounded-[2rem] border border-dashed border-slate-300 bg-white/60 p-10 text-center', 'rounded-lg border border-dashed border-line bg-surface p-10 text-center');
rep('rounded-[2rem] border border-amber-200 bg-amber-50 p-10 text-center', 'rounded-lg border border-warning/25 bg-warning-soft p-10 text-center');

fs.writeFileSync(P, t, 'utf8');
console.log(misses.length ? 'MISSES:\n' + misses.join('\n') : 'partA2 applied');