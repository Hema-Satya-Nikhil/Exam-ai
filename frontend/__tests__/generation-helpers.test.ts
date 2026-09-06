import { isTerminal, progressPercent, stageLabel } from '../lib/generation-progress';

describe('generation progress helpers', () => {
  it('derives faculty-facing stage labels from sanitized steps', () => {
    expect(stageLabel(null, 'queued')).toMatch(/Preparing your question paper/);
    expect(stageLabel('Generating question 3 of 11', 'running')).toBe('Generating question');
    expect(stageLabel('Validating & saving question 3 of 11', 'running')).toBe('Validating question');
    expect(stageLabel('Ready for review', 'completed')).toBe('Paper ready for review');
    expect(stageLabel('Generation failed', 'failed')).toBe('Generation failed');
  });

  it('computes percent from completed/total and clamps completion', () => {
    expect(progressPercent('running', 2, 11, null)).toBe(18);
    expect(progressPercent('completed', 11, 11, 100)).toBe(100);
    expect(progressPercent('queued', 0, null, null)).toBe(0);
  });

  it('flags terminal statuses', () => {
    expect(isTerminal('running')).toBe(false);
    expect(isTerminal('completed')).toBe(true);
    expect(isTerminal('failed')).toBe(true);
    expect(isTerminal('cancelled')).toBe(true);
  });
});
