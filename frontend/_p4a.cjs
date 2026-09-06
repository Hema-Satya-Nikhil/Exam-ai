const fs = require('fs');
const P = 'components/review/paper-review.tsx';
let t = fs.readFileSync(P, 'utf8').replace(/\r\n/g, '\n');
let misses = [];
function rep(from, to) {
  const n = t.split(from).length - 1;
  if (n === 0) { misses.push(from.slice(0, 70).replace(/\n/g, ' ')); return; }
  t = t.split(from).join(to);
}

// --- imports: drop GlassCard, add Badge + Skeleton ---
rep("import { GlassCard } from '@/components/ui/glass-card';",
    "import { Badge } from '@/components/ui/badge';\nimport { Skeleton } from '@/components/ui/skeleton';");

// --- authLoading branch -> skeleton ---
rep(
  '      <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.9),_rgba(226,232,240,0.6)_34%,_rgba(203,213,225,0.25)_70%,_rgba(15,23,42,0.04))]">\n        <Loader2 className="h-8 w-8 animate-spin text-slate-500" />\n      </main>',
  '      <main className="flex min-h-screen items-center justify-center bg-background px-6">\n        <div className="w-full max-w-md space-y-3">\n          <Skeleton className="h-7 w-56" />\n          <Skeleton className="h-4 w-80 max-w-full" />\n          <Skeleton className="h-24 w-full" />\n          <Skeleton className="h-24 w-full" />\n        </div>\n      </main>'
);

// --- outer main chrome ---
rep(
  '<main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.92),_rgba(226,232,240,0.68)_36%,_rgba(203,213,225,0.26)_70%,_rgba(15,23,42,0.04))] text-slate-900">',
  '<main className="min-h-screen bg-background text-text-primary">'
);

fs.writeFileSync(P, t, 'utf8');
console.log(misses.length ? 'MISSES:\n' + misses.join('\n') : 'partA1 applied');