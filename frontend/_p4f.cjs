const fs = require('fs');
const P = 'components/review/paper-review.tsx';
let t = fs.readFileSync(P, 'utf8').replace(/\r\n/g, '\n');
let misses = [];
function rep(from, to) {
  const n = t.split(from).length - 1;
  if (n === 0) { misses.push(from.slice(0, 70).replace(/\n/g, ' ')); return; }
  t = t.split(from).join(to);
}

// --- edit textarea ---
rep('        <textarea value={editText} onChange={(event) => onEditTextChange(event.target.value)}\n          className="mt-3 w-full rounded-xl border border-slate-300 p-3 text-sm outline-none focus:border-slate-900" rows={3} />',
    '        <textarea value={editText} onChange={(event) => onEditTextChange(event.target.value)}\n          aria-label="Question text"\n          data-testid="edit-textarea"\n          className="mt-3 w-full rounded-[0.5rem] border border-line bg-surface p-3 text-body text-text-primary outline-none transition-colors duration-micro focus:border-primary focus:ring-2 focus:ring-primary/20" rows={3} />');

// --- question text ---
rep('<p data-testid="question-text" className="mt-3 text-sm leading-7 text-slate-800">{question.question_text || \'No question text yet.\'}</p>',
    '<p data-testid="question-text" className="mt-3 whitespace-pre-wrap text-body leading-7 text-text-primary">{question.question_text || \'No question text yet.\'}</p>');

// --- instruction input (KEEP as <input>) ---
rep('        <input value={instruction} onChange={(event) => onInstructionChange(event.target.value)}\n          placeholder="Optional: what to improve in the rewrite"\n          className="min-w-52 flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-400" />',
    '        <input value={instruction} onChange={(event) => onInstructionChange(event.target.value)}\n          placeholder="Optional: what to improve in the rewrite"\n          aria-label="Regeneration instructions"\n          data-testid="regen-input"\n          className="min-w-52 flex-1 rounded-[0.5rem] border border-line bg-surface px-3 py-2 text-body text-text-primary outline-none transition-colors duration-micro focus:border-primary focus:ring-2 focus:ring-primary/20" />');

// --- regenerate button ---
rep('        <button type="button" onClick={onRegenerate} disabled={locked || regenPending}\n          className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-800 transition hover:bg-slate-100 disabled:opacity-50">\n          <RefreshCw className="h-3.5 w-3.5" /> Regenerate\n        </button>',
    '        <button type="button" onClick={onRegenerate} disabled={locked || regenPending}\n          className="inline-flex items-center gap-1.5 rounded-[0.5rem] border border-primary/40 bg-transparent px-4 py-2 text-metadata font-semibold text-primary transition-colors duration-micro hover:bg-primary-soft/60 disabled:opacity-50">\n          <RefreshCw className="h-3.5 w-3.5" /> Regenerate\n        </button>');

// --- edit-mode flag + locked regen hint ---
rep(
  '      <h2 className="mt-3 text-section-heading text-text-primary">{question.topic || `Question ${displayLabel}`}</h2>',
  '      <div className="mt-3 flex flex-wrap items-center gap-2">\n        <h2 className="text-section-heading text-text-primary">{question.topic || `Question ${displayLabel}`}</h2>\n        {isEditing ? (\n          <span className="rounded-pill border border-warning/30 bg-warning-soft px-2.5 py-0.5 text-metadata font-medium text-warning" data-testid="unsaved-changes">Unsaved changes</span>\n        ) : null}\n        {locked ? (\n          <span className="text-metadata text-danger" data-testid="locked-hint">This question is locked and cannot be regenerated.</span>\n        ) : null}\n      </div>'
);

fs.writeFileSync(P, t, 'utf8');
console.log(misses.length ? 'MISSES:\n' + misses.join('\n') : 'partD2 applied');