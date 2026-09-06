import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';

import HomePage from '@/app/page';

jest.mock('@/contexts/auth-context', () => ({
  useAuth: jest.fn(),
}));
import { useAuth } from '@/contexts/auth-context';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

// ButtonLink renders a next/link — stub the Image-free Link is unnecessary;
// next/link works in jsdom, so no mock needed.

describe('Landing page', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useAuth as jest.Mock).mockReturnValue({ user: null, loading: false });
  });

  it('renders the hero heading and product kicker', () => {
    render(<HomePage />);
    expect(screen.getByRole('heading', { level: 1, name: /create better question papers with ai/i })).toBeInTheDocument();
    expect(screen.getAllByText('ExamCraft AI').length).toBeGreaterThanOrEqual(1);
  });

  it('primary CTA links to the create flow and secondary CTA anchors to how-it-works', () => {
    render(<HomePage />);
    const ctas = screen.getAllByRole('link', { name: /create question paper/i });
    expect(ctas.length).toBeGreaterThanOrEqual(2); // hero + closing strip
    for (const cta of ctas) {
      expect(cta).toHaveAttribute('href', '/create');
    }
    expect(screen.getByRole('link', { name: /explore how it works/i })).toHaveAttribute('href', '#how-it-works');
  });

  it('shows the four value propositions', () => {
    render(<HomePage />);
    for (const title of ['Syllabus-aware', 'Structured', 'Reviewable', 'Exportable']) {
      expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
    }
  });

  it('shows the four-step workflow section', () => {
    render(<HomePage />);
    expect(screen.getByRole('heading', { name: /how it works/i })).toBeInTheDocument();
    expect(screen.getByText('Upload syllabus')).toBeInTheDocument();
    expect(screen.getByText('Configure exam')).toBeInTheDocument();
    expect(screen.getByText('Generate questions')).toBeInTheDocument();
    expect(screen.getByText('Review & export')).toBeInTheDocument();
  });

  it('labels the exam-structure highlight as an illustrative example', () => {
    render(<HomePage />);
    const aside = screen.getByRole('complementary', { name: /example exam structure/i });
    expect(aside).toBeInTheDocument();
    expect(screen.getByText(/illustrative example/i)).toBeInTheDocument();
    expect(screen.getByText('Part A')).toBeInTheDocument();
    expect(screen.getByText('Part B')).toBeInTheDocument();
  });

  it('footer shows login/create-account links for signed-out visitors', () => {
    render(<HomePage />);
    expect(screen.getByRole('navigation', { name: /footer/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Login' })).toHaveAttribute('href', '/login');
    expect(screen.getByRole('link', { name: 'Create account' })).toHaveAttribute('href', '/login');
  });

  it('footer shows workspace links for signed-in users instead of auth links', () => {
    (useAuth as jest.Mock).mockReturnValue({
      user: { user_id: 'u1', email: 'f@x.com', full_name: 'F', roles: ['faculty'] },
      loading: false,
    });
    render(<HomePage />);
    expect(screen.queryByRole('link', { name: 'Login' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Create Paper' })).toHaveAttribute('href', '/create');
  });
});
