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

describe('GenerationProgressCard', () => {
  it('shows the preparing heading and question X of Y while running', () => {
    render(<GenerationProgressCard job={snapshot()} onResume={() => {}} resuming={false} />);
    expect(screen.getByTestId('gen-heading')).toHaveTextContent('Preparing your question paper');
    expect(screen.getByTestId('gen-count')).toHaveTextContent('Question 3 of 11');
    expect(screen.getByTestId('gen-stage')).toHaveTextContent('Generating question');
    expect(screen.getByTestId('gen-bar')).toHaveAttribute('aria-valuenow', '25');
  });

  it('marks completion at 100% when the job completes', () => {
    render(<GenerationProgressCard job={snapshot({
      status: 'completed',
      current_step: 'Ready for review',
      completed_questions: 11,
      progress_percent: 100,
      paper_id: 'p1'
    })} onResume={() => {}} resuming={false} />);
    expect(screen.getByTestId('gen-bar')).toHaveAttribute('aria-valuenow', '100');
    expect(screen.getByTestId('gen-stage')).toHaveTextContent('Paper ready for review');
  });

  it('shows the sanitized failure and a resume action when failed', () => {
    const onResume = jest.fn();
    render(<GenerationProgressCard job={snapshot({
      status: 'failed',
      error_message: 'NVIDIA request failed while generating question generation.'
    })} onResume={onResume} resuming={false} />);
    expect(screen.getByTestId('job-error')).toHaveTextContent(/NVIDIA request failed/i);
    fireEvent.click(screen.getByTestId('job-resume'));
    expect(onResume).toHaveBeenCalledTimes(1);
  });
});
