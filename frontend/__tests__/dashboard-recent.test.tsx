import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DashboardPage from '@/app/dashboard/page';
import { fetchRecentPapers } from '@/lib/api';

jest.mock('@/lib/api', () => ({
  fetchRecentPapers: jest.fn(),
}));

jest.mock('@/contexts/auth-context', () => ({
  useAuth: () => ({ user: mockAuthUser, loading: false }),
}));

jest.mock('@/components/layout/topbar', () => ({
  TopBar: () => <div data-testid="topbar" />,
}));

jest.mock('@/components/ui/glass-card', () => ({
  GlassCard: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const mockFetch = fetchRecentPapers as jest.Mock;

let mockAuthUser: any = null;

const compositePaper = {
  id: 'p1',
  title: 'MID 1 - OSE2E2A593',
  subject: 'Operating Systems',
  exam_type: 'MID 1',
  total_marks: 50,
  duration_minutes: 110,
  status: 'approved',
  created_at: '2026-08-29T13:11:15Z',
  updated_at: '2026-08-29T13:11:15Z',
};

const legacyPaper = {
  id: 'p0',
  title: 'quiz-paper',
  subject: 'Data Warehousing and Data Mining',
  exam_type: 'QUIZ',
  total_marks: 20,
  duration_minutes: 40,
  status: 'draft',
  created_at: '2026-08-28T10:00:00Z',
  updated_at: '2026-08-28T10:00:00Z',
};

beforeEach(() => {
  mockFetch.mockReset();
  mockAuthUser = null;
});

test('shows the loading state while fetching', async () => {
  mockFetch.mockReturnValue(new Promise(() => {}));
  render(<DashboardPage />);
  expect(screen.getByText('Loading recent papers...')).toBeInTheDocument();
});

test('shows the empty state when no papers exist', async () => {
  mockFetch.mockResolvedValue([]);
  render(<DashboardPage />);
  await waitFor(() => expect(screen.getByText('No papers yet')).toBeInTheDocument());
  expect(screen.getByText('Create your first question paper to get started.')).toBeInTheDocument();
});

test('shows the error state with retry when the API fails', async () => {
  mockFetch.mockRejectedValue(new Error('network'));
  render(<DashboardPage />);
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Unable to load recent papers.'));
  expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
});

test('retry after API failure loads the papers', async () => {
  mockFetch.mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce([compositePaper]);
  render(<DashboardPage />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
  await waitFor(() => expect(screen.getByText('Operating Systems')).toBeInTheDocument());
});

test('renders a single recent paper with summary metadata', async () => {
  mockFetch.mockResolvedValue([compositePaper]);
  render(<DashboardPage />);
  await waitFor(() => {
    expect(screen.getByText('Operating Systems')).toBeInTheDocument();
    expect(screen.getByText(/MID 1 · 50 Marks · 110 Minutes/)).toBeInTheDocument();
  });
});

test('renders multiple papers newest-first (API order preserved)', async () => {
  mockFetch.mockResolvedValue([compositePaper, legacyPaper]);
  render(<DashboardPage />);
  await waitFor(() => expect(screen.getByText('Operating Systems')).toBeInTheDocument());
  const list = screen.getByTestId('recent-papers-list');
  const items = within(list).getAllByRole('listitem');
  expect(items).toHaveLength(2);
  expect(items[0]).toHaveTextContent('Operating Systems');
  expect(items[1]).toHaveTextContent('Data Warehousing and Data Mining');
});

test('renders composite and legacy papers alike', async () => {
  mockFetch.mockResolvedValue([legacyPaper]);
  render(<DashboardPage />);
  await waitFor(() => expect(screen.getByText('Data Warehousing and Data Mining')).toBeInTheDocument());
  expect(screen.getByText(/QUIZ · 20 Marks · 40 Minutes/)).toBeInTheDocument();
});

test('Open Review navigates to the correct review page', async () => {
  mockFetch.mockResolvedValue([compositePaper]);
  render(<DashboardPage />);
  await waitFor(() => expect(screen.getByText('Operating Systems')).toBeInTheDocument());
  const link = screen.getByRole('link', { name: 'Open Review' });
  expect(link).toHaveAttribute('href', '/review?paper_id=p1');
});

test('falls back to the title when subject is missing', async () => {
  mockFetch.mockResolvedValue([{ ...compositePaper, subject: null }]);
  render(<DashboardPage />);
  await waitFor(() => expect(screen.getByText('MID 1 - OSE2E2A593')).toBeInTheDocument());
});


test('hides the People and Access link for non-admin users', async () => {
  mockFetch.mockResolvedValue([compositePaper]);
  render(<DashboardPage />);
  await waitFor(() => expect(screen.getByText('Operating Systems')).toBeInTheDocument());
  expect(screen.queryByTestId('people-access-link')).not.toBeInTheDocument();
});

test('shows the People and Access link for admins', async () => {
  mockAuthUser = { roles: ['admin'] };
  mockFetch.mockResolvedValue([compositePaper]);
  render(<DashboardPage />);
  await waitFor(() => expect(screen.getByText('Operating Systems')).toBeInTheDocument());
  const link = screen.getByTestId('people-access-link');
  expect(link).toHaveAttribute('href', '/admin');
});

test('renders a personalized greeting header with the faculty name', async () => {
  mockAuthUser = { roles: ['faculty'], full_name: 'Priya Sharma', email: 'priya@examcraft.ai' };
  mockFetch.mockResolvedValue([compositePaper]);
  render(<DashboardPage />);
  await waitFor(() => expect(screen.getByText('Operating Systems')).toBeInTheDocument());
  const heading = screen.getByRole('heading', { level: 1 });
  expect(heading.textContent).toMatch(/Priya Sharma/);
  expect(heading.textContent).toMatch(/^(Good morning|Good afternoon|Good evening|Welcome)/);
  expect(screen.getByText('Create, review, and manage your examination papers.')).toBeInTheDocument();
});

test('shows a generic greeting when no user is signed in', async () => {
  mockFetch.mockResolvedValue([compositePaper]);
  render(<DashboardPage />);
  await waitFor(() => expect(screen.getByText('Operating Systems')).toBeInTheDocument());
  expect(['Welcome', 'Good morning', 'Good afternoon', 'Good evening']).toContain(
    screen.getByRole('heading', { level: 1 }).textContent
  );
});

test('primary CTA links to the create wizard', () => {
  mockFetch.mockReturnValue(new Promise(() => {}));
  render(<DashboardPage />);
  // The CTA appears in the header, quick actions and closing strip — all /create.
  const ctas = screen.getAllByRole('link', { name: 'Create Question Paper' });
  expect(ctas.length).toBeGreaterThanOrEqual(1);
  ctas.forEach((cta) => expect(cta).toHaveAttribute('href', '/create'));
});

test('quick actions cover create, recent papers and review routes', () => {
  mockFetch.mockReturnValue(new Promise(() => {}));
  render(<DashboardPage />);
  expect(screen.getByText('Quick actions')).toBeInTheDocument();
  const section = screen.getByText('Quick actions').closest('section') as HTMLElement;
  const scoped = within(section);
  expect(scoped.getByText('Create Question Paper')).toBeInTheDocument();
  expect(scoped.getByText('Recent Papers')).toBeInTheDocument();
  expect(scoped.getByText('Review Papers')).toBeInTheDocument();
  const hrefs = scoped.getAllByRole('link').map((l) => l.getAttribute('href'));
  expect(hrefs).toContain('/create');
  expect(hrefs).toContain('/dashboard#recent');
  expect(hrefs).toContain('/review');
});

test('workflow card renders the six-step guidance without fabricating state', () => {
  mockFetch.mockResolvedValue([compositePaper]);
  render(<DashboardPage />);
  expect(screen.getByText('Your workflow')).toBeInTheDocument();
  ['Syllabus', 'Exam structure', 'Blueprint & Bloom', 'Generate', 'Review', 'Export'].forEach((label) => {
    expect(screen.getAllByText(label).length).toBeGreaterThan(0);
  });
  // static guidance: no fabricated completion claims
  expect(screen.queryByText(/completed/i)).not.toBeInTheDocument();
});

test('recent paper rows render the real status via StatusBadge', async () => {
  mockFetch.mockResolvedValue([compositePaper]);
  render(<DashboardPage />);
  await waitFor(() => expect(screen.getByText('Approved')).toBeInTheDocument());
  expect(screen.getByText(/Generated Aug 29, 2026/)).toBeInTheDocument();
});

test('responsive dashboard structure: quick actions grid and stacked content', () => {
  mockFetch.mockReturnValue(new Promise(() => {}));
  render(<DashboardPage />);
  const section = screen.getByText('Quick actions').closest('section') as HTMLElement;
  const grid = section.querySelector('div');
  expect(grid?.className).toContain('sm:grid-cols-2');
  expect(grid?.className).toContain('xl:grid-cols-4');
});
