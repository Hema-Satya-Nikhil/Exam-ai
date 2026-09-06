import { render, screen, within } from '@testing-library/react';
import { PaperWizard } from '@/components/wizard/paper-wizard';

jest.mock('@/lib/api', () => ({
  confirmSyllabus: jest.fn(),
  getGenerationJob: jest.fn(),
  queueGenerationJob: jest.fn(),
  resumeGenerationJob: jest.fn(),
  uploadModelPaper: jest.fn(),
  uploadSyllabus: jest.fn(),
  uploadUnitMaterial: jest.fn(),
  validateBlueprint: jest.fn()
}));

jest.mock('@/contexts/auth-context', () => ({
  useAuth: () => ({ user: { roles: ['faculty'], full_name: 'Test Faculty', email: 't@x.ai' }, loading: false })
}));

function getStepperNav() {
  return screen.getByRole('navigation', { name: 'Paper creation steps' });
}

describe('Wizard chrome', () => {
  test('renders the eight-step sequence in order', () => {
    render(<PaperWizard />);
    const items = within(getStepperNav()).getAllByRole('listitem');
    expect(items).toHaveLength(8);
    const labels = ['Subject & Exam', 'Syllabus', 'Unit Materials', 'Paper Pattern', 'Question Structure', 'Blueprint & Bloom', 'Generate', 'Review & Export'];
    labels.forEach((label, index) => {
      expect(within(items[index]).getByText(label)).toBeInTheDocument();
    });
  });

  test('marks the first step as current and others as pending/optional', () => {
    render(<PaperWizard />);
    expect(screen.getByTestId('step-current')).toBeInTheDocument();
    // 8 steps total: 1 current + 6 pending + 1 optional (Unit Materials)
    expect(screen.getAllByTestId('step-pending')).toHaveLength(6);
    expect(screen.getByTestId('step-optional')).toBeInTheDocument();
    expect(getStepperNav().querySelector('[aria-current="step"]')).not.toBeNull();
  });

  test('shows the compact mobile step header with progress semantics', () => {
    render(<PaperWizard />);
    const progress = screen.getByLabelText('Wizard progress');
    const header = progress.closest('div.lg\\:hidden') || progress.parentElement;
    expect(within(header as HTMLElement).getByText('Step 1 of 8')).toBeInTheDocument();
    expect(progress).toHaveAttribute('aria-valuenow', '13');
    expect(within(header as HTMLElement).getByText('Subject & Exam')).toBeInTheDocument();
  });

  test('flags the optional step in the stepper', () => {
    render(<PaperWizard />);
    expect(screen.getByTestId('step-optional')).toBeInTheDocument();
    expect(screen.getAllByText('Optional').length).toBeGreaterThanOrEqual(1);
  });

  test('renders the wizard heading and title', () => {
    render(<PaperWizard />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Create Your Question Paper');
  });

  test('step 1 shows the live summary with the configured values', () => {
    render(<PaperWizard />);
    const summary = screen.getByTestId('step1-summary');
    expect(within(summary).getByText('70 Marks')).toBeInTheDocument();
    expect(within(summary).getByText('180 Minutes')).toBeInTheDocument();
    // nothing fabricated: no units/subject/exam chips before the user enters them
    expect(within(summary).queryByText(/Units/)).not.toBeInTheDocument();
  });

  test('navigation: Back is disabled on the first step and Continue is gated', () => {
    render(<PaperWizard />);
    expect(screen.getByRole('button', { name: 'Back' })).toBeDisabled();
    expect(screen.getByTestId('wizard-next')).toBeDisabled();
    expect(screen.getByText('Step 1 of 8', { selector: 'p' })).toBeInTheDocument();
  });
});
