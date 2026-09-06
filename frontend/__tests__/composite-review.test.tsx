import { render, screen, fireEvent, within } from '@testing-library/react';

import { PaperReview } from '@/components/review/paper-review';
import {
  clusterGroupsByChoice,
  hasPartLevelChoice,
  isCompositePaper,
  questionActionKey,
  questionIdentity,
} from '../lib/composite-review';

jest.mock('next/navigation', () => ({
  useSearchParams: () => ({ get: () => 'paper-1' }),
}));

jest.mock('@/contexts/auth-context', () => ({
  useAuth: () => ({
    user: { user_id: 'u1', email: 'f@e.com', roles: ['faculty'], is_active: true },
    loading: false,
  }),
}));

const regenerateMutate = jest.fn();
const lockMutate = jest.fn();
const unlockMutate = jest.fn();
let draftFixture: any;

jest.mock('@/hooks/use-paper-review', () => ({
  usePaperDraft: () => ({ data: draftFixture, isLoading: false, isError: false }),
  usePaperApproval: () => ({ mutate: jest.fn(), isPending: false }),
  usePaperExport: () => ({ mutate: jest.fn(), isPending: false }),
  usePaperLock: () => ({ mutate: lockMutate, isPending: false }),
  usePaperUnlock: () => ({ mutate: unlockMutate, isPending: false }),
  usePaperQuestionUpdate: () => ({ mutate: jest.fn(), isPending: false }),
  usePaperRegeneration: () => ({ mutate: regenerateMutate, isPending: false }),
}));

function partAQuestions() {
  return Array.from({ length: 10 }, (_, i) => ({
    question_number: i + 1,
    section: 'Part A',
    marks: 2,
    unit: (i % 2) + 1,
    topic: `Unit ${i + 1}`,
    bloom_level: 'L2',
    difficulty: 'easy',
    question_type: 'conceptual',
    exam_part: 'short_answer',
    group_number: null,
    part_label: null,
    choice_group_id: null,
    choice_member_id: null,
    locked: false,
    question_text: `Short answer question ${i + 1}`,
  }));
}

function compositeDraft(): any {
  const part = (
    question_number: number, group_number: number, part_label: string,
    topic: string, bloom: string, cg: string | null, cm: string | null,
    locked = false, text?: string,
  ) => ({
    exam_part: 'main', group_number,
    part_label, question_number, marks: 5, unit: ((question_number % 2) + 1),
    topic, bloom_level: bloom, difficulty: 'medium', question_type: 'conceptual',
    choice_group_id: cg, choice_member_id: cm, locked,
    question_text: text ?? `Group ${group_number} part ${part_label}`,
  });
  return {
    id: 'v-1',
    title: 'OS Composite Mid',
    status: 'under_review',
    paper_id: 'paper-1',
    paper_json: {
      total_marks: 50,
      duration_minutes: 110,
      status: 'under_review',
      questions: [],
      sections: [],
      parts: {
        part_a: {
          name: 'PART A - SHORT ANSWER',
          total_marks: 20,
          duration_minutes: 20,
          questions: partAQuestions(),
        },
        part_b: {
          name: 'PART B - MAIN PAPER',
          total_marks: 30,
          duration_minutes: 90,
          groups: [
            { group_number: 1, choice_group: null, parts: [
              part(11, 1, 'a', 'Processes', 'L2', null, null),
              part(12, 1, 'b', 'Scheduling', 'L3', null, null),
            ] },
            { group_number: 2, choice_group: 'cg1', parts: [
              part(13, 2, 'a', 'Deadlock', 'L4', 'cg1', 'm1', true, 'OR side one'),
              part(14, 2, 'b', 'Memory', 'L4', 'cg1', 'm2', false, 'OR side two'),
            ] },
            { group_number: 3, choice_group: 'cg1', parts: [
              part(15, 3, 'a', 'Paging', 'L3', 'cg1', 'm3'),
              part(16, 3, 'b', 'Virtual memory', 'L3', 'cg1', 'm4'),
            ] },
          ],
        },
      },
    },
  };
}

function flatDraft(): any {
  return {
    id: 'v-2',
    title: 'Legacy flat paper',
    status: 'draft',
    paper_id: 'paper-2',
    paper_json: {
      questions: [
        { question_number: 1, marks: 5, unit: 1, bloom_level: 'L2', difficulty: 'medium',
          question_type: 'conceptual', locked: false, question_text: 'Flat question one' },
      ],
    },
  };
}

export { compositeDraft, flatDraft };

describe('composite Review UI (Phase 4)', () => {
  beforeEach(() => {
    regenerateMutate.mockClear();
    lockMutate.mockClear();
    unlockMutate.mockClear();
    draftFixture = compositeDraft();
  });

  it('renders the PART A banner and all 10 short-answer questions in order', () => {
    render(<PaperReview />);
    const banners = screen.getAllByTestId('part-banner');
    expect(banners[0]).toHaveTextContent(/PART A/i);
    expect(banners[0]).toHaveTextContent('10 × 2 Marks');
    expect(banners[0]).toHaveTextContent('20 Minutes');

    const partASection = screen.getByTestId('part-a-section');
    expect(partASection.querySelectorAll('[data-testid="question-card"]').length).toBe(10);
    expect(screen.getByText('Short answer question 1')).toBeInTheDocument();
    expect(screen.getByText('Short answer question 10')).toBeInTheDocument();
  });

  it('renders the PART B banner and every question group with part labels', () => {
    render(<PaperReview />);
    const banners = screen.getAllByTestId('part-banner');
    expect(banners[1]).toHaveTextContent(/PART B/i);
    expect(banners[1]).toHaveTextContent('30 Marks');
    expect(banners[1]).toHaveTextContent('90 Minutes');

    const headers = screen.getAllByTestId('group-header').map((h) => h.textContent);
    expect(headers).toEqual(
      expect.arrayContaining([
        expect.stringContaining('Question Group 1'),
        expect.stringContaining('Question Group 2'),
        expect.stringContaining('Question Group 3'),
      ]),
    );
    const labels = screen.getAllByTestId('part-label').map((n) => n.textContent);
    expect(labels).toEqual(expect.arrayContaining(['1(a) · 5 Marks', '2(b) · 5 Marks']));
    expect(screen.getByText('Group 1 part a')).toBeInTheDocument();
    expect(screen.getByText('Group 3 part b')).toBeInTheDocument();
  });

  it('renders explicit OR dividers between part-level alternatives only', () => {
    render(<PaperReview />);
    // One divider inside each 2-part group (part-level OR).
    expect(screen.getAllByTestId('or-divider').length).toBe(3);
    // Choice clusters come from persisted choice_group_id, not numbering.
    const alternatives = screen.getAllByTestId('or-alternative');
    expect(alternatives.length).toBe(2); // groups 2 and 3 share cg1
    expect(alternatives[0]).toHaveTextContent('Question Group 2');
    expect(alternatives[1]).toHaveTextContent('Question Group 3');
  });

  it('shows persisted choice metadata on alternatives', () => {
    render(<PaperReview />);
    const card = screen.getByText('OR side two').closest('[data-testid="question-card"]');
    expect(card!.textContent).toContain('Choice: cg1');
    const lockedCard = screen.getByText('OR side one').closest('[data-testid="question-card"]');
    expect(lockedCard!.textContent).toContain('Locked');
    expect(card!.textContent).toContain('Unlocked');
  });

  it('builds the Part A action key from persisted composite metadata', () => {
    const question = compositeDraft().paper_json.parts.part_a.questions[4];
    expect(questionActionKey(questionIdentity(question))).toBe('short_answer:q5');
  });

  it('builds the Part B action key from persisted composite metadata', () => {
    const question = compositeDraft().paper_json.parts.part_b.groups[0].parts[0];
    expect(questionActionKey(questionIdentity(question))).toBe('main:g1:a');
  });

  it('builds the OR alternative action key from persisted composite metadata', () => {
    const question = compositeDraft().paper_json.parts.part_b.groups[1].parts[1];
    expect(questionActionKey(questionIdentity(question))).toBe('main:g2:b');
  });

  it('keeps regeneration instructions isolated by composite action key', () => {
    render(<PaperReview />);
    const cards = screen.getAllByTestId('question-card');
    const targetCard = cards.find((card) => card.textContent?.includes('OR side two'))!;
    const otherCard = cards.find((card) => card.textContent?.includes('Group 3 part a'))!;

    fireEvent.change(targetCard.querySelector('input')!, {
      target: { value: 'make it more numeric' },
    });
    fireEvent.click(within(targetCard).getByRole('button', { name: /regenerate/i }));

    const payload = regenerateMutate.mock.calls[0][0];
    expect(payload).toEqual({
      paper_id: 'paper-1',
      question: { exam_part: 'main', question_number: 14, group_number: 2, part_label: 'b' },
      instructions: 'make it more numeric',
    });
    expect(otherCard.querySelector('input')).toHaveValue('');
  });

  it('invokes lock and unlock with composite question identity', () => {
    render(<PaperReview />);
    const unlockedCard = screen.getByText('OR side two').closest('[data-testid="question-card"]')!;
    fireEvent.click(screen.getAllByRole('button', { name: /lock/i })[0]);
    expect(lockMutate).toHaveBeenCalledWith(
      {
        paper_id: 'paper-1',
        question: { exam_part: 'short_answer', question_number: 1, group_number: null, part_label: null },
      },
      expect.any(Object),
    );

    const lockedButton = unlockedCard.querySelectorAll('button')[1];
    fireEvent.click(lockedButton);
    expect(lockMutate).toHaveBeenCalledWith(
      {
        paper_id: 'paper-1',
        question: { exam_part: 'main', question_number: 14, group_number: 2, part_label: 'b' },
      },
      expect.any(Object),
    );

    const lockedCard = screen.getByText('OR side one').closest('[data-testid="question-card"]')!;
    fireEvent.click(lockedCard.querySelectorAll('button')[1]);
    expect(unlockMutate).toHaveBeenCalledWith(
      {
        paper_id: 'paper-1',
        question: { exam_part: 'main', question_number: 13, group_number: 2, part_label: 'a' },
      },
      expect.any(Object),
    );
  });

  it('shows a helpful 404 error from review actions', () => {
    regenerateMutate.mockImplementationOnce((_payload, options) => {
      options.onError?.(new Error('Question not found'));
    });

    render(<PaperReview />);
    const card = screen.getByText('OR side two').closest('[data-testid="question-card"]') as HTMLElement;
    fireEvent.click(within(card).getByRole('button', { name: /regenerate/i }));
    expect(screen.getByText('Question not found')).toBeInTheDocument();
  });

  it('keeps the legacy flat rendering for non-composite papers', () => {
    draftFixture = flatDraft();
    render(<PaperReview />);
    expect(screen.queryByTestId('composite-exam')).not.toBeInTheDocument();
    expect(screen.queryAllByTestId('part-banner').length).toBe(0);
    expect(screen.getByText('Flat question one')).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Persisted validation record (paper_json.validation) + export gating
  // -------------------------------------------------------------------------

  it('shows final-check passed for a clean composite validation record', () => {
    draftFixture = compositeDraft();
    draftFixture.paper_json.validation = { passed: true, errors: [], warnings: [] };
    render(<PaperReview />);
    expect(screen.getByTestId('final-check-passed')).toBeInTheDocument();
    expect(screen.queryByTestId('final-check-blocked')).not.toBeInTheDocument();
  });

  it('shows composite validation errors as blocking', () => {
    draftFixture = compositeDraft();
    draftFixture.paper_json.validation = {
      passed: false,
      errors: [
        { severity: 'error', code: 'part_b_attempted_mismatch',
          message: 'Part B attempted marks do not match the configured total.' },
      ],
      warnings: [],
    };
    render(<PaperReview />);
    expect(screen.getByTestId('final-check-blocked')).toBeInTheDocument();
    expect(screen.getByText(/Part B attempted marks do not match/i)).toBeInTheDocument();
    expect(screen.queryByTestId('final-check-passed')).not.toBeInTheDocument();
  });

  it('shows composite warnings separately from blocking errors', () => {
    draftFixture = compositeDraft();
    draftFixture.paper_json.validation = {
      passed: true,
      errors: [],
      warnings: [
        { severity: 'warning', code: 'topic_pool_exhausted',
          message: 'A topic was reused because the unit lists no further topics.' },
      ],
    };
    render(<PaperReview />);
    expect(screen.getByTestId('final-check-passed')).toBeInTheDocument();
    const warnings = screen.getByTestId('final-check-warnings');
    expect(warnings).toHaveTextContent('Warnings');
    expect(warnings).toHaveTextContent(/A topic was reused because the unit lists no further topics/i);
  });

  it('enables PDF/DOCX export when composite validation is clean', () => {
    draftFixture = compositeDraft();
    draftFixture.paper_json.validation = { passed: true, errors: [], warnings: [] };
    render(<PaperReview />);
    const pdf = screen.getByRole('button', { name: /pdf/i });
    const docx = screen.getByRole('button', { name: /docx/i });
    expect(pdf).not.toBeDisabled();
    expect(docx).not.toBeDisabled();
  });

  it('disables export when composite validation has blocking errors', () => {
    draftFixture = compositeDraft();
    draftFixture.paper_json.validation = {
      passed: false,
      errors: [{ severity: 'error', code: 'x', message: 'Blocking problem.' }],
      warnings: [],
    };
    render(<PaperReview />);
    expect(screen.getAllByText('Resolve the highlighted validation issues before exporting.').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /pdf/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /docx/i })).toBeDisabled();
  });

  it('keeps legacy flat validation using its existing ValidationSummary shape', () => {
    draftFixture = flatDraft();
    draftFixture.paper_json.validation = {
      passed: false,
      issues: [
        { severity: 'error', code: 'exact_duplicate_topic', message: 'Duplicate topic in Section A.' },
      ],
    };
    render(<PaperReview />);
    expect(screen.getByTestId('final-check-blocked')).toBeInTheDocument();
    expect(screen.getByText('Duplicate topic in Section A.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /pdf/i })).toBeDisabled();
  });

  it('helper: clusters groups strictly by persisted choice_group_id', () => {
    const groups = compositeDraft().paper_json.parts.part_b.groups;
    const clusters = clusterGroupsByChoice(groups);
    expect(clusters.filter((c) => c.choiceGroupId === 'cg1')[0].groups.map((g) => g.group_number))
      .toEqual([2, 3]);
    expect(clusters.filter((c) => c.choiceGroupId === null)[0].groups[0].group_number).toBe(1);
    expect(hasPartLevelChoice(groups[0])).toBe(false);
    expect(hasPartLevelChoice(groups[1])).toBe(true);
    expect(isCompositePaper(flatDraft().paper_json)).toBe(false);
  });
});
