const fs = require('fs');
const P = 'components/review/paper-review.tsx';
let t = fs.readFileSync(P, 'utf8').replace(/\r\n/g, '\n');
let misses = [];
function rep(from, to) {
  const n = t.split(from).length - 1;
  if (n === 0) { misses.push(from.slice(0, 70).replace(/\n/g, ' ')); return; }
  t = t.split(from).join(to);
}

// --- PartBanner: stronger academic banner ---
rep(
  '      <div data-testid="part-banner"\n      className="rounded-2xl bg-slate-950 px-5 py-4 text-white shadow-md">\n      <p className="text-xs font-bold uppercase tracking-[0.28em] text-slate-400">{name}</p>\n      <p className="mt-1 text-lg font-semibold">{meta}</p>\n    </div>',
  '      <div data-testid="part-banner"\n      className="rounded-lg border border-primary/20 bg-primary px-5 py-5 text-white shadow-low">\n      <p className="text-metadata font-bold uppercase tracking-[0.28em] text-white/85">{name}</p>\n      <p className="mt-1 text-lg font-semibold">{meta}</p>\n    </div>'
);

// --- OrDivider: more prominent OR ---
rep(
  '    <div role="separator" aria-label="OR" data-testid="or-divider"\n      className="my-4 flex items-center gap-3">\n      <span className="h-px flex-1 bg-slate-300" />\n      <span data-testid="or-label"\n        className="rounded-full border-2 border-slate-900 bg-white px-5 py-1 text-sm font-extrabold uppercase tracking-[0.3em] text-slate-900 shadow-sm">\n        OR\n      </span>\n      <span className="h-px flex-1 bg-slate-300" />\n    </div>',
  '    <div role="separator" aria-label="OR" data-testid="or-divider"\n      className="my-5 flex items-center gap-3">\n      <span className="h-0.5 flex-1 bg-slate-300" />\n      <span data-testid="or-label"\n        className="rounded-pill border-2 border-primary bg-surface px-6 py-1.5 text-small font-extrabold uppercase tracking-[0.3em] text-primary shadow-low">\n        OR\n      </span>\n      <span className="h-0.5 flex-1 bg-slate-300" />\n    </div>'
);

// --- Pill: compact token chip ---
rep(
  'function Pill({ children }: { children: React.ReactNode }) {\n  return <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">{children}</span>;\n}',
  'function Pill({ children }: { children: React.ReactNode }) {\n  return <span className="rounded-pill border border-line bg-surface px-2.5 py-0.5 text-metadata font-medium text-text-secondary">{children}</span>;\n}'
);

// --- StatCard: token ---
rep(
  '    <div className="rounded-3xl border border-slate-200/70 bg-white/80 px-4 py-3 shadow-sm">\n      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>\n      <p className="mt-1 text-xl font-semibold text-slate-950">{value}</p>\n    </div>',
  '    <div className="rounded-lg border border-line bg-surface px-4 py-3 shadow-low">\n      <p className="text-metadata uppercase tracking-[0.18em] text-text-muted">{label}</p>\n      <p className="mt-1 text-body font-semibold text-text-primary">{value}</p>\n    </div>'
);

fs.writeFileSync(P, t, 'utf8');
console.log(misses.length ? 'MISSES:\n' + misses.join('\n') : 'partC applied');