const fs = require('fs');
const P = 'components/review/paper-review.tsx';
let t = fs.readFileSync(P, 'utf8').replace(/\r\n/g, '\n');
let misses = [];
function rep(from, to) {
  const n = t.split(from).length - 1;
  if (n === 0) { misses.push(from.slice(0, 70).replace(/\n/g, ' ')); return; }
  t = t.split(from).join(to);
}

// --- QuestionArticle card chrome ---
rep('<article data-testid="question-card" className="rounded-3xl border border-white/70 bg-white/75 p-5 shadow-sm">',
    '<article data-testid="question-card" className="rounded-lg border border-line bg-surface p-5 shadow-low">');
rep('className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/60 pb-3"',
    'className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3"');
rep('className="flex flex-wrap items-center gap-2 border-t border-slate-200/60 pt-3"',
    'className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3"');
rep('          <span data-testid="question-number"\n            className="rounded-full bg-slate-950 px-3 py-1 text-xs font-semibold tracking-[0.2em] text-white">',
    '          <span data-testid="question-number"\n            className="rounded-sm bg-primary px-3 py-1 text-metadata font-semibold tracking-[0.2em] text-white">');
rep('            <span data-testid="lock-state" className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">\n              <Lock className="h-3 w-3" /> Locked\n            </span>',
    '            <span data-testid="lock-state" className="inline-flex items-center gap-1 rounded-pill border border-success/30 bg-success-soft px-3 py-1 text-metadata font-medium text-success">\n              <Lock className="h-3 w-3" /> Locked\n            </span>');
rep('            <span data-testid="unlock-state" className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">Unlocked</span>',
    '            <span data-testid="unlock-state" className="rounded-pill border border-warning/30 bg-warning-soft px-3 py-1 text-metadata font-medium text-warning">Unlocked</span>');
rep('            <button type="button" onClick={onSaveEdit}\n              className="rounded-full bg-slate-950 px-3 py-1 text-xs font-semibold text-white transition hover:bg-slate-800">\n              Save\n            </button>',
    '            <button type="button" onClick={onSaveEdit}\n              className="rounded-[0.5rem] bg-primary px-3 py-1 text-metadata font-semibold text-white transition-colors duration-micro hover:bg-primary-hover">\n              Save\n            </button>');
rep('            <button type="button" onClick={onEditStart}\n              className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100">\n              <Edit3 className="h-3.5 w-3.5" /> Edit\n            </button>',
    '            <button type="button" onClick={onEditStart}\n              className="inline-flex items-center gap-1.5 rounded-[0.5rem] border border-line bg-surface px-3 py-1 text-metadata font-medium text-text-secondary transition-colors duration-micro hover:bg-slate-50">\n              <Edit3 className="h-3.5 w-3.5" /> Edit\n            </button>');
rep('            <button type="button" onClick={onToggleLock}\n            disabled={regenPending}\n            className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50">\n            {locked ? <Unlock className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}\n            {locked ? \'Unlock\' : \'Lock\'}\n          </button>',
    '            <button type="button" onClick={onToggleLock}\n            disabled={regenPending}\n            className="inline-flex items-center gap-1.5 rounded-[0.5rem] border border-line bg-surface px-3 py-1 text-metadata font-medium text-text-secondary transition-colors duration-micro hover:bg-slate-50 disabled:opacity-50">\n            {locked ? <Unlock className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}\n            {locked ? \'Unlock\' : \'Lock\'}\n          </button>');
rep('<h2 className="mt-3 text-base font-semibold text-slate-950">{question.topic || `Question ${displayLabel}`}</h2>',
    '<h2 className="mt-3 text-section-heading text-text-primary">{question.topic || `Question ${displayLabel}`}</h2>');
rep('<p className="mt-0.5 text-xs text-slate-500">', '<p className="mt-0.5 text-metadata text-text-muted">');

fs.writeFileSync(P, t, 'utf8');
console.log(misses.length ? 'MISSES:\n' + misses.join('\n') : 'partD1 applied');