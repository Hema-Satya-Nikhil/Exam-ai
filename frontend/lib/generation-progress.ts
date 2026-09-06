// Pure helpers for the async generation-job polling UI (no React, no fetch).

export type GenerationJobStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

export const POLL_INTERVAL_MS = 1500;

export const TERMINAL_STATUSES: GenerationJobStatus[] = ['completed', 'failed', 'cancelled'];

export function isTerminal(status: string): boolean {
  return TERMINAL_STATUSES.includes(status as GenerationJobStatus);
}

/** Overall progress: job percent when the server provides one, else derived. */
export function progressPercent(
  status: string,
  completed: number,
  total: number | null,
  serverPercent: number | null
): number {
  if (status === 'completed') return 100;
  if (serverPercent !== null && serverPercent !== undefined) return serverPercent;
  if (!total) return 0;
  return Math.min(100, Math.round((completed / total) * 100));
}

/** Faculty-facing stage label derived from the sanitized server step. */
export function stageLabel(step: string | null, status: string): string {
  if (status === 'completed') return 'Paper ready for review';
  if (status === 'failed') return 'Generation failed';
  if (status === 'cancelled') return 'Generation cancelled';
  if (!step || status === 'queued') return 'Preparing your question paper…';
  const s = step.toLowerCase();
  if (s.includes('validating blueprint')) return 'Validating blueprint';
  if (s.includes('resum')) return 'Resuming';
  if (s.includes('generating part a')) return 'Generating Part A';
  if (s.includes('generating part b')) return 'Generating Part B';
  if (s.includes('generating question')) return 'Generating question';
  if (s.includes('validating') || s.includes('saving')) return 'Validating question';
  return 'Generating question';
}

// ---------------------------------------------------------------------------
// Phase 5 — premium generation experience (pure, UI-agnostic helpers)
// ---------------------------------------------------------------------------

export type GenerationStageState = 'done' | 'current' | 'pending';

export interface GenerationStage {
  key: string;
  label: string;
  state: GenerationStageState;
}

export type GenerationPartState = 'pending' | 'active' | 'done';

/** Big friendly title for the current job state (never technical terms). */
export function stateTitle(status: string): string {
  switch (status) {
    case 'queued':
      return 'Preparing your question paper';
    case 'running':
      return 'Generating your question paper';
    case 'completed':
      return 'Your question paper is ready';
    case 'failed':
      return 'We couldn’t finish your question paper';
    case 'cancelled':
      return 'Generation cancelled';
    default:
      return 'Preparing your question paper';
  }
}

/** One-line reassurance copy for the current job state. */
export function stateDescription(status: string): string {
  switch (status) {
    case 'queued':
      return 'Setting up your examination structure.';
    case 'running':
      return 'Your questions are being generated and saved as they complete.';
    case 'completed':
      return 'Your questions have been generated and validated.';
    case 'failed':
      return 'Something interrupted the generation process.';
    case 'cancelled':
      return 'This generation was cancelled. You can start a new one whenever you are ready.';
    default:
      return 'Setting up your examination structure.';
  }
}

/**
 * Stage timeline derived ONLY from the real job state / sanitized step.
 * A stage is marked complete only when the job state supports it — history is
 * never fabricated: an active job claims at most one current stage.
 */
export function stageTimeline(step: string | null, status: string): GenerationStage[] {
  const s = (step ?? '').toLowerCase();
  const done = status === 'completed';
  const running = status === 'running';
  const started = done || running || status === 'failed' || status === 'cancelled';
  const generating = s.includes('generating');
  const validating = s.includes('validat');
  return [
    { key: 'prepare', label: 'Preparing', state: started ? 'done' : 'current' },
    {
      key: 'structure',
      label: 'Building question structure',
      state: done || (running && (generating || validating)) ? 'done' : 'pending',
    },
    {
      key: 'generate',
      label: 'Generating questions',
      state: done ? 'done' : running && generating && !validating ? 'current' : 'pending',
    },
    {
      key: 'validate',
      label: 'Validating paper',
      state: done ? 'done' : running && validating ? 'current' : 'pending',
    },
    { key: 'review', label: 'Preparing review', state: done ? 'done' : 'pending' },
  ];
}

/** Part A / Part B activity derived from the real step text only. */
export function partActivity(
  step: string | null,
  status: string,
): { partA: GenerationPartState; partB: GenerationPartState } {
  if (status === 'completed') return { partA: 'done', partB: 'done' };
  const s = (step ?? '').toLowerCase();
  return {
    partA: s.includes('part b') ? 'done' : s.includes('part a') ? 'active' : 'pending',
    partB: s.includes('part b') ? 'active' : 'pending',
  };
}

/**
 * Real "6 / 8" label for a part — null when the API provides no part counts
 * (the UI then shows a status word instead of fabricating sub-progress).
 */
export function partCountLabel(
  part: { total_questions: number; completed_questions: number } | null | undefined,
): string | null {
  if (!part || !part.total_questions) return null;
  return `${Math.min(part.completed_questions, part.total_questions)} / ${part.total_questions}`;
}
