import { Badge } from '@/components/ui/badge';

interface PartBannerProps {
  name: string;
  meta: string;
  questionCount?: number;
  marksPerQuestion?: number;
  totalMarks?: number;
  durationMinutes?: number | null;
}

/**
 * Premium section banner for Part A / Part B.
 * Example: "PART A — SHORT ANSWER" + "10 × 2 Marks · 20 Marks · 20 Minutes"
 */
export function PartBanner({
  name, meta, questionCount, marksPerQuestion, totalMarks, durationMinutes,
}: PartBannerProps) {
  return (
    <div data-testid="part-banner" className="rounded-lg border border-line bg-surface p-4 shadow-low">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-[0.28em] text-text-muted">
          {name}
        </p>
        <Badge tone="neutral" className="text-xs">
          {meta}
        </Badge>
      </div>
    </div>
  );
}
