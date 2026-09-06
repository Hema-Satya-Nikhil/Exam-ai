'use client';

import Link from 'next/link';
import { CheckCircle2, CircleDashed, Loader2, RefreshCw, Sparkles } from 'lucide-react';

import {
  partActivity,
  partCountLabel,
  progressPercent,
  stageLabel,
  stageTimeline,
  stateDescription,
  stateTitle,
} from '@/lib/generation-progress';
import type { GenerationJobSnapshot, GenerationPartProgress } from '@/lib/api';
import type { GenerationPartState } from '@/lib/generation-progress';
import type { Route } from 'next';

const PART_STATE_LABEL: Record<GenerationPartState, string> = {
  pending: 'Pending',
  active: 'In progress',
  done: 'Done',
};

export function GenerationProgressCard({
  job,
  onResume,
  resuming,
  onRetry,
  reviewHref
}: {
  job: GenerationJobSnapshot;
  onResume: () => void;
  resuming: boolean;
  onRetry?: () => void;
  reviewHref?: Route;
}) {
  const total = job.total_questions ?? 0;
  const completed = job.completed_questions ?? 0;
  const percent = progressPercent(job.status, completed, total, job.progress_percent);
  const stage = stageLabel(job.current_step, job.status);
  const timeline = stageTimeline(job.current_step, job.status);
  const partsState = partActivity(job.current_step, job.status);
  const active = job.status === 'queued' || job.status === 'running';
  const indeterminate = active && total === 0 && !job.progress_percent;

  // Heading keeps the established copy for queued/running jobs; terminal
  // states switch to their state-specific title.
  const heading =
    job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled'
      ? stateTitle(job.status)
      : 'Preparing your question paper…';

  // Question activity from REAL snapshot fields only.
  const currentQuestion =
    job.current_question ?? (job.status === 'running' ? completed + 1 : null);
  let activity: string | null = null;
  if (job.status === 'running' && total > 0 && currentQuestion) {
    const stepText = (job.current_step ?? '').toLowerCase();
    const partPrefix = stepText.includes('part b')
      ? 'Part B · '
      : stepText.includes('part a')
        ? 'Part A · '
        : '';
    activity = `${partPrefix}Generating Question ${Math.min(currentQuestion, total)} of ${total}`;
  }

  // Part rows appear only when the job provides a real part signal.
  const hasPartSignal =
    Boolean(job.part_a || job.part_b) || /part a|part b/i.test(job.current_step ?? '');

  return (
    <div
      className="mt-6 rounded-2xl border border-white/75 bg-white/70 p-5 shadow-glass-soft backdrop-blur-md sm:p-6"
      data-testid="generation-progress"
      aria-live="polite"
    >
      {/* Header */}
      <div className="flex items-center gap-3">
        {active ? (
          <Loader2 className="h-5 w-5 animate-spin text-primary" aria-hidden="true" />
        ) : (
          <Sparkles className="h-5 w-5 text-text-muted" aria-hidden="true" />
        )}
        <p className="text-small font-semibold text-text-primary" data-testid="gen-heading">
          {heading}
        </p>
      </div>
      <p className="mt-1 text-small text-text-secondary" data-testid="gen-state-desc">
        {stateDescription(job.status)}
      </p>

      {/* Progress — indeterminate preparation state when no real numbers exist */}
      {indeterminate ? (
        <div className="mt-4">
          <div
            className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200/70"
            role="progressbar"
            aria-label="Preparing your question paper"
          >
            <div className="h-full w-1/3 rounded-full bg-primary/60 animate-pulse" data-testid="gen-bar" />
          </div>
          <p className="mt-2 text-metadata text-text-muted" data-testid="gen-count">
            Preparing…
          </p>
        </div>
      ) : (
        <>
          <div className="mt-4 flex items-baseline justify-between gap-3">
            <p className="text-metadata text-text-muted" data-testid="gen-percent">
              {percent}% complete
            </p>
            {total > 0 ? (
              <p className="text-small font-semibold text-text-primary" data-testid="gen-count">
                Question {Math.min(completed + (job.status === 'completed' ? 0 : 1), total)} of{' '}
                {total}
                {job.status === 'completed' ? '' : ` · ${completed} saved`}
              </p>
            ) : null}
          </div>
          <div
            className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-slate-200/70"
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Generation progress"
            data-testid="gen-bar"
          >
            <div
              className="h-full rounded-full bg-primary transition-all duration-panel ease-standard"
              style={{ width: `${percent}%` }}
            />
          </div>
        </>
      )}

      {/* Current activity */}
      <p className="mt-3 text-small text-text-secondary">
        Stage: <span className="font-medium text-text-primary" data-testid="gen-stage">{stage}</span>
      </p>
      {activity ? (
        <p className="mt-1 text-small text-text-secondary" data-testid="gen-activity">
          {activity}
        </p>
      ) : null}

      {/* Reassurance */}
      {active ? (
        <p className="mt-2 text-metadata text-text-muted" data-testid="gen-reassurance">
          Your syllabus, exam structure, and question constraints are being applied.
        </p>
      ) : null}

      {/* Part A / Part B — only with a real part signal; counts only when provided */}
      {hasPartSignal ? (
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <PartRow label="Part A" state={partsState.partA} counts={job.part_a} testid="gen-part-a" />
          <PartRow label="Part B" state={partsState.partB} counts={job.part_b} testid="gen-part-b" />
        </div>
      ) : null}

      {/* Stage timeline */}
      <ol className="mt-4 space-y-1.5 border-t border-line pt-3" data-testid="gen-timeline">
        {timeline.map((entry) => (
          <li key={entry.key} className="flex items-center gap-2 text-small">
            {entry.state === 'done' ? (
              <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" />
            ) : entry.state === 'current' ? (
              <span className="inline-flex h-4 w-4 items-center justify-center" aria-hidden="true">
                <span className="h-2 w-2 rounded-full bg-primary" />
              </span>
            ) : (
              <CircleDashed className="h-4 w-4 text-text-muted" aria-hidden="true" />
            )}
            <span
              className={
                entry.state === 'done'
                  ? 'text-text-secondary'
                  : entry.state === 'current'
                    ? 'font-semibold text-text-primary'
                    : 'text-text-muted'
              }
            >
              {entry.label}
            </span>
          </li>
        ))}
      </ol>

      {/* Completed */}
      {job.status === 'completed' ? (
        <div
          className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-success/25 bg-success-soft px-4 py-3"
          data-testid="gen-completed"
          role="status"
        >
          <div>
            <p className="flex items-center gap-2 text-small font-semibold text-success">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> Your question paper is ready
            </p>
            <p className="mt-0.5 text-metadata text-success">
              {total > 0 ? `${total} questions · ` : ''}Your questions have been generated and
              validated.
            </p>
          </div>
          {reviewHref ? (
            <Link
              href={reviewHref}
              data-testid="gen-review-cta"
              className="inline-flex items-center rounded-[0.5rem] bg-primary px-4 py-2 text-metadata font-semibold text-white transition-colors duration-micro hover:bg-primary-hover"
            >
              Review Question Paper
            </Link>
          ) : null}
        </div>
      ) : null}

      {/* Failed */}
      {job.status === 'failed' ? (
        <div
          className="mt-4 rounded-lg border border-danger/25 bg-danger-soft px-4 py-3 text-small text-danger"
          data-testid="job-error"
          role="alert"
        >
          <p className="font-semibold">Generation couldn’t be completed.</p>
          <p className="mt-1 text-metadata">Something interrupted the generation process.</p>
          {job.error_message ? (
            <p className="mt-2 text-metadata leading-5 text-danger/90">{job.error_message}</p>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onResume}
              disabled={resuming}
              className="inline-flex items-center gap-2 rounded-[0.5rem] border border-danger/40 bg-surface px-4 py-1.5 text-metadata font-semibold text-danger transition-colors duration-micro hover:bg-surface-elevated disabled:opacity-60"
              data-testid="job-resume"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> Resume generation
            </button>
            {onRetry ? (
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex items-center gap-2 rounded-[0.5rem] border border-line bg-surface px-4 py-1.5 text-metadata font-semibold text-text-secondary transition-colors duration-micro hover:bg-slate-50"
                data-testid="job-retry"
              >
                Try again
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Cancelled */}
      {job.status === 'cancelled' ? (
        <div
          className="mt-4 rounded-lg border border-warning/25 bg-warning-soft px-4 py-3"
          data-testid="job-cancelled"
          role="status"
        >
          <p className="text-small font-semibold text-warning">Generation cancelled</p>
          <p className="mt-1 text-metadata text-warning">
            No further questions will be generated for this job.
          </p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-2 rounded-[0.5rem] border border-warning/40 bg-surface px-4 py-1.5 text-metadata font-semibold text-warning transition-colors duration-micro hover:bg-surface-elevated"
              data-testid="job-cancelled-retry"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> Start a new generation
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function PartRow({
  label,
  state,
  counts,
  testid,
}: {
  label: string;
  state: GenerationPartState;
  counts?: GenerationPartProgress | null;
  testid: string;
}) {
  const countLabel = partCountLabel(counts);
  const partPercent =
    counts && counts.total_questions
      ? Math.min(100, Math.round((counts.completed_questions / counts.total_questions) * 100))
      : null;
  return (
    <div
      className="rounded-md border border-line bg-surface-elevated px-3 py-2.5"
      data-testid={testid}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-metadata font-semibold uppercase tracking-[0.14em] text-text-secondary">
          {label}
        </p>
        <p
          className={`text-metadata font-medium ${
            state === 'done'
              ? 'text-success'
              : state === 'active'
                ? 'text-primary'
                : 'text-text-muted'
          }`}
          data-testid={`${testid}-state`}
        >
          {countLabel ?? PART_STATE_LABEL[state]}
        </p>
      </div>
      {countLabel && partPercent !== null ? (
        <div
          className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200/70"
          role="progressbar"
          aria-valuenow={partPercent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${label} progress`}
          data-testid={`${testid}-bar`}
        >
          <div
            className="h-full rounded-full bg-primary transition-all duration-panel ease-standard"
            style={{ width: `${partPercent}%` }}
          />
        </div>
      ) : null}
    </div>
  );
}
