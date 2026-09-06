import { Suspense } from 'react';
import { AppShell } from '@/components/layout/app-shell';
import { PaperReview } from '@/components/review/paper-review';

export default function ReviewPage() {
  return (
    <AppShell>
    <Suspense fallback={<div className="p-8 text-center text-slate-600">Loading faculty review workspace...</div>}>
      <PaperReview />
    </Suspense>
    </AppShell>

  );
}
