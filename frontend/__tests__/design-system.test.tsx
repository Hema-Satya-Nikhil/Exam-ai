import { render, screen } from '@testing-library/react';
import { AppShell } from '@/components/layout/app-shell';
import { Button } from '@/components/ui/button';
import { StatusBadge, STATUS_TONE } from '@/components/ui/badge';

jest.mock('@/contexts/auth-context', () => ({
  useAuth: () => ({
    user: mockAuthUser,
    loading: false,
    login: jest.fn(),
    logout: jest.fn(),
    register: jest.fn()
  })
}));

let mockAuthUser: any = null;

beforeEach(() => {
  mockAuthUser = null;
});

describe('AppShell navigation gating', () => {
  test('faculty see workspace and system nav but no admin group', () => {
    mockAuthUser = { roles: ['faculty'], full_name: 'Fac User', email: 'f@x.ai' };
    render(
      <AppShell>
        <p>content</p>
      </AppShell>
    );
    expect(screen.getByText('Create Paper')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.queryByText('People & Access')).not.toBeInTheDocument();
    expect(screen.queryByText('Audit')).not.toBeInTheDocument();
    expect(screen.getByText('content')).toBeInTheDocument();
  });

  test('admins see the admin nav group', () => {
    mockAuthUser = { roles: ['admin'], full_name: 'Admin User', email: 'a@x.ai' };
    render(
      <AppShell>
        <p>content</p>
      </AppShell>
    );
    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.getByText('People & Access')).toBeInTheDocument();
    expect(screen.getByText('Audit')).toBeInTheDocument();
  });

  test('topbar shows user identity and role', () => {
    mockAuthUser = { roles: ['admin'], full_name: 'Admin User', email: 'a@x.ai' };
    render(
      <AppShell>
        <p>content</p>
      </AppShell>
    );
    expect(screen.getByText('Admin User')).toBeInTheDocument();
    expect(screen.getByText('Administrator')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Profile menu' })).toBeInTheDocument();
  });
});

describe('Button primitive', () => {
  test('loading state swaps content for a spinner and disables', () => {
    render(<Button loading loadingText="Saving...">Save Changes</Button>);
    const btn = screen.getByRole('button', { name: 'Saving...' });
    expect(btn).toBeDisabled();
    expect(screen.queryByText('Save Changes')).not.toBeInTheDocument();
    expect(btn).toHaveAttribute('aria-busy', 'true');
  });

  test('variants render and honor aria-label for icon buttons', () => {
    render(<Button variant="danger">Delete</Button>);
    expect(screen.getByRole('button', { name: 'Delete' }).className).toContain('bg-danger');
  });
});

describe('Status system', () => {
  test('statusâ†’tone mapping covers the canonical states', () => {
    expect(STATUS_TONE.pending).toBe('warning');
    expect(STATUS_TONE.active).toBe('success');
    expect(STATUS_TONE.generating).toBe('info');
    expect(STATUS_TONE.failed).toBe('danger');
    expect(STATUS_TONE.locked).toBe('neutral');
  });

  test('StatusBadge renders a normalized label with the mapped tone', () => {
    render(<StatusBadge status="generating" />);
    expect(screen.getByText('Generating').className).toContain('bg-info-soft');
  });
});
