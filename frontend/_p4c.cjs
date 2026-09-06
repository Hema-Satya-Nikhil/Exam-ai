const fs = require('fs');
const P = 'components/review/paper-review.tsx';
let t = fs.readFileSync(P, 'utf8').replace(/\r\n/g, '\n');
let misses = [];
function rep(from, to) {
  const n = t.split(from).length - 1;
  if (n === 0) { misses.push(from.slice(0, 70).replace(/\n/g, ' ')); return; }
  t = t.split(from).join(to);
}

// --- imports: add StatusBadge ---
rep("import { Badge } from '@/components/ui/badge';",
    "import { Badge, StatusBadge } from '@/components/ui/badge';");

// --- paper summary card inserted above the stat grid ---
rep(
  '              <div className="grid gap-3 sm:grid-cols-4">\n                <StatCard label="Status" value={statusLabel(status)} />',
  '              <div className="rounded-lg border border-line bg-surface p-4 shadow-low" data-testid="paper-summary">\n                <p className="text-metadata font-semibold uppercase tracking-[0.14em] text-text-muted">Paper summary</p>\n                <div className="mt-3 flex flex-wrap gap-2">\n                  {(paperJson.subject_name || paperJson.subject || draft?.subject) ? (\n                    <Badge tone="primary">{paperJson.subject_name || paperJson.subject || draft?.subject}</Badge>\n                  ) : null}\n                  {(paperJson.exam_type || paperJson.exam_title || draft?.exam_type) ? (\n                    <Badge tone="neutral">{paperJson.exam_type || paperJson.exam_title || draft?.exam_type}</Badge>\n                  ) : null}\n                  <Badge tone="neutral">{totalMarks} Marks</Badge>\n                  <Badge tone="neutral">{paperJson.duration_minutes || \'—\'} Minutes</Badge>\n                  <Badge tone="neutral">{questions.length} Questions</Badge>\n                  <StatusBadge status={status} />\n                </div>\n              </div>\n              <div className="grid gap-3 sm:grid-cols-4">\n                <StatCard label="Status" value={statusLabel(status)} />'
);

// --- feedback box -> token tint + role=alert for errors ---
rep(
  '                <div\n                  className={`rounded-2xl border px-4 py-3 text-sm ${\n                    feedback.tone === \'ok\' ? \'border-emerald-200 bg-emerald-50 text-emerald-800\' : \'border-red-200 bg-red-50 text-red-800\'\n                  }`}\n                >\n                  {feedback.message}\n                </div>',
  '                <div\n                  role={feedback.tone === \'error\' ? \'alert\' : \'status\'}\n                  className={`rounded-lg border px-4 py-3 text-small ${\n                    feedback.tone === \'ok\' ? \'border-success/25 bg-success-soft text-success\' : \'border-danger/25 bg-danger-soft text-danger\'\n                  }`}\n                >\n                  {feedback.message}\n                </div>'
);

// --- GlassCard (Final Check + Export) -> token card ---
t = t.split('<GlassCard>').join('<div className="rounded-lg border border-line bg-surface p-5 shadow-low">');
t = t.split('</GlassCard>').join('</div>');

// --- or-alternative / group container classes ---
rep('className="rounded-3xl border border-slate-200/80 bg-white/70 p-5"', 'className="rounded-lg border border-line bg-surface p-5 shadow-low"');
rep('className="text-sm font-bold uppercase tracking-[0.2em] text-slate-700"', 'className="text-small font-bold uppercase tracking-[0.2em] text-text-secondary"');
rep('className="rounded-full border border-slate-900 bg-white px-3 py-0.5 text-xs font-bold text-slate-900"', 'className="rounded-pill border border-line bg-surface px-3 py-0.5 text-metadata font-bold text-text-primary"');

// --- empty-legacy + no-questions branch classes ---
rep('rounded-3xl border border-dashed border-slate-300 bg-white/60 p-10 text-center', 'rounded-lg border border-dashed border-line bg-surface p-10 text-center');

fs.writeFileSync(P, t, 'utf8');
console.log(misses.length ? 'MISSES:\n' + misses.join('\n') : 'partB applied');