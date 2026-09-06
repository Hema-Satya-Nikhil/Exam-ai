import { render, screen, fireEvent } from '@testing-library/react';

import { GenerationProgressCard } from '../components/wizard/generation-progress';
import type { GenerationJobSnapshot } from '../lib/api';

function snapshot(overrides: Partial<GenerationJobSnapshot> = {}): GenerationJobSnapshot {
  return {
    id: 'job-1',
    status: 'running',
    current_step: 'Generating question 3 of 11',
    progress_percent: 25,
    retry_count: 0,
    error_message: null,
    paper_id: null,
    created_by: 'u1',
    total_questions: 11,
    completed_questions: 2,
    current_question: 3,
    created_at: null,
    started_at: null,
    finished_at: null,
    updated_at: null,
    ...overrides
  };
}

describe('Generation experience (Phase 5)', () => {
  it('1. queued state shows preparing copy and the stage timeline', () => {
    render(<GenerationProgressCard job={snapshot({ status: 'queued', current_step: 'Queued', progress_percent: 0 })} onResume={() => {}} resuming={false} />);
    expect(screen.getByTestId('gen-heading')).toHaveTextContent('Preparing your question paper');
    expect(screen.getByTestId('gen-state-desc')).toHaveTextContent('Setting up your examination structure.');
    const timeline = screen.getByTestId('gen-timeline');
    expect(timeline).toHaveTextContent('Preparing');
    expect(timeline).toHaveTextContent('Generating questions');
  });

  it('2. running state keeps the established heading and shows the state description', () => {
    render(<GenerationProgressCard job={snapshot()} onResume={() => {}} resuming={false} />);
    expect(screen.getByTestId('gen-heading')).toHaveTextContent('Preparing your question paper');
    expect(screen.getByTestId('gen-state-desc')).toHaveTextContent(/generated and saved/i);
  });

  it('3. progress bar exposes the real server percent', () => {
    render(<GenerationProgressCard job={snapshot()} onResume={() => {}} resuming={false} />);
    expect(screen.getByTestId('gen-bar')).toHaveAttribute('aria-valuenow', '25');
    expect(screen.getByTestId('gen-percent')).toHaveTextContent('25% complete');
  });

  it('4. question count uses the real snapshot numbers', () => {
    render(<GenerationProgressCard job={snapshot()} onResume={() => {}} resuming={false} />);
    expect(screen.getByTestId('gen-count')).toHaveTextContent('Question 3 of 11');
  });

  it('5. Part A shows real completed/total counts when the API provides them', () => {
    render(
      <GenerationProgressCard
        job={snapshot({
          current_step: 'Generating Part A question 9',
          part_a: { total_questions: 10, completed_questions: 10, status: 'generating' },
          part_b: { total_questions: 8, completed_questions: 0, status: 'pending' }
        })}
        onResume={() => {}} resuming={false}
      />
    );
    expect(screen.getByTestId('gen-part-a-state')).toHaveTextContent('10 / 10');
  });

  it('6. Part B shows real counts and a real progress bar', () => {
    render(
      <GenerationProgressCard
        job={snapshot({
          current_step: 'Generating Part B',
          part_b: { total_questions: 8, completed_questions: 6, status: 'generating' }
        })}
        onResume={() => {}} resuming={false}
      />
    );
    expect(screen.getByTestId('gen-part-b-state')).toHaveTextContent('6 / 8');
    expect(screen.getByTestId('gen-part-b-bar')).toHaveAttribute('aria-valuenow', '75');
  });

  it('7. current stage maps technical steps to friendly labels', () => {
    render(<GenerationProgressCard job={snapshot({ current_step: 'Generating Part B question 12' })} onResume={() => {}} resuming={false} />);
    expect(screen.getByTestId('gen-stage')).toHaveTextContent('Generating Part B');
  });

  it('8. failed state shows the friendly failure alert with role=alert', () => {
    render(<GenerationProgressCard job={snapshot({ status: 'failed', error_message: 'Request timeout while generating question generation.' })} onResume={() => {}} resuming={false} onRetry={() => {}} />);
    const error = screen.getByTestId('job-error');
    expect(error).toHaveAttribute('role', 'alert');
    expect(error).toHaveTextContent(/Generation couldn’t be completed/i);
    expect(error).toHaveTextContent(/Something interrupted the generation process/i);
  });

  it('9. retry button invokes the retry handler', () => {
    const onRetry = jest.fn();
    render(<GenerationProgressCard job={snapshot({ status: 'failed', error_message: 'boom' })} onResume={() => {}} resuming={false} onRetry={onRetry} />);
    fireEvent.click(screen.getByTestId('job-retry'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('10. resume action stays available on failure', () => {
    const onResume = jest.fn();
    render(<GenerationProgressCard job={snapshot({ status: 'failed', error_message: 'boom' })} onResume={onResume} resuming={false} />);
    fireEvent.click(screen.getByTestId('job-resume'));
    expect(onResume).toHaveBeenCalledTimes(1);
  });

  it('11. cancelled state shows the cancelled panel and a fresh-start action', () => {
    const onRetry = jest.fn();
    render(<GenerationProgressCard job={snapshot({ status: 'cancelled', current_step: 'Cancelled by user' })} onResume={() => {}} resuming={false} onRetry={onRetry} />);
    expect(screen.getByTestId('job-cancelled')).toHaveTextContent('Generation cancelled');
    fireEvent.click(screen.getByTestId('job-cancelled-retry'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('12 + 13. completed state shows the ready panel and a review CTA to the paper', () => {
    render(
      <GenerationProgressCard
        job={snapshot({ status: 'completed', current_step: 'Ready for review', completed_questions: 11, progress_percent: 100, paper_id: 'p1' })}
        onResume={() => {}} resuming={false} reviewHref="/review?paper_id=p1"
      />
    );
    expect(screen.getByTestId('gen-completed')).toHaveTextContent('Your question paper is ready');
    expect(screen.getByTestId('gen-review-cta')).toHaveAttribute('href', '/review?paper_id=p1');
    expect(screen.getByTestId('gen-bar')).toHaveAttribute('aria-valuenow', '100');
  });

  it('14. active states expose no technical terminology', () => {
    const { container } = render(<GenerationProgressCard job={snapshot()} onResume={() => {}} resuming={false} />);
    const text = container.textContent ?? '';
    expect(text).not.toMatch(/nvidia|llm|backend|database|\bapi\b|job id/i);
  });

  it('15. accessibility: progressbar semantics, live region, timeline', () => {
    render(<GenerationProgressCard job={snapshot()} onResume={() => {}} resuming={false} />);
    const card = screen.getByTestId('generation-progress');
    expect(card).toHaveAttribute('aria-live', 'polite');
    const bar = screen.getByRole('progressbar', { name: 'Generation progress' });
    expect(bar).toHaveAttribute('aria-valuemin', '0');
    expect(bar).toHaveAttribute('aria-valuemax', '100');
    expect(screen.getByTestId('gen-timeline')).toBeInTheDocument();
  });

  it('16. mobile layout: full-width bar and responsive part grid, no overflow', () => {
    render(
      <GenerationProgressCard
        job={snapshot({ current_step: 'Generating Part B', part_b: { total_questions: 8, completed_questions: 6, status: 'generating' } })}
        onResume={() => {}} resuming={false}
      />
    );
    const partGrid = screen.getByTestId('gen-part-a').parentElement;
    expect(partGrid?.className).toContain('sm:grid-cols-2');
    expect(document.querySelector('[data-testid="generation-progress"] .w-full')).not.toBeNull();
  });
});
