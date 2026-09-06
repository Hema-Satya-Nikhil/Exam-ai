import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { useAuth } from '@/contexts/auth-context';
import SettingsPage from '@/app/settings/page';

jest.mock('@/contexts/auth-context', () => ({
  useAuth: jest.fn(),
}));

jest.mock('@/lib/api', () => ({
  getCurrentUser: jest.fn(),
}));

jest.mock('next/navigation', () => ({
  useSearchParams: () => ({ get: () => null }),
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

jest.mock('@/components/layout/app-shell', () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const mockUser = (overrides = {}) => ({
  user_id: 'usr-1',
  email: 'faculty@example.com',
  full_name: 'Test User',
  is_active: true,
  roles: ['faculty'],
  ...overrides,
});

const facultyUser = mockUser({ email: 'faculty@example.com', roles: ['faculty'] });
const adminUser = mockUser({ email: 'admin@example.com', roles: ['admin'] });
const disabledUser = mockUser({ is_active: false, roles: ['faculty'] });

describe('SettingsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('1. renders the settings header', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: facultyUser, loading: false });
    render(<SettingsPage />);
    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByText(/Manage your account and application preferences/i)).toBeInTheDocument();
  });

  it('2. renders account information for authenticated user', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: facultyUser, loading: false });
    render(<SettingsPage />);
    expect(screen.getByText('Test User')).toBeInTheDocument();
    expect(screen.getByText('faculty@example.com')).toBeInTheDocument();
  });

  it('3. role-aware display shows correct role badge', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: facultyUser, loading: false });
    render(<SettingsPage />);
    expect(screen.getByText('Faculty')).toBeInTheDocument();
  });

  it('3b. admin role badge displayed for admins', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: adminUser, loading: false });
    render(<SettingsPage />);
    expect(screen.getByText('Admin')).toBeInTheDocument();
  });

  it('4. account status shown as Active for enabled user', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: facultyUser, loading: false });
    render(<SettingsPage />);
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('4b. account status shown as Disabled for disabled user', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: disabledUser, loading: false });
    render(<SettingsPage />);
    expect(screen.getByText('Disabled')).toBeInTheDocument();
  });

  it('5. quick actions show Create Paper for all roles', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: facultyUser, loading: false });
    render(<SettingsPage />);
    expect(screen.getByText('Create a new paper')).toBeInTheDocument();
    expect(screen.getByText('Create a new paper').closest('a')).toHaveAttribute('href', '/create');
  });

  it('6. faculty sees View your papers shortcut', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: facultyUser, loading: false });
    render(<SettingsPage />);
    expect(screen.getByText('View your papers')).toBeInTheDocument();
    expect(screen.getByText('View your papers').closest('a')).toHaveAttribute('href', '/dashboard');
  });

  it('7. admin sees Manage people & access shortcut', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: adminUser, loading: false });
    render(<SettingsPage />);
    expect(screen.getByText(/Manage people/i)).toBeInTheDocument();
        expect(screen.getByText(/Manage people/i).closest('a')).toHaveAttribute('href', '/admin');
  });

  it('8. faculty does NOT see Manage people & access shortcut', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: facultyUser, loading: false });
    render(<SettingsPage />);
    expect(screen.queryByText(/Manage people/i)).not.toBeInTheDocument();
  });

  it('9. admin does NOT see View your papers shortcut', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: adminUser, loading: false });
    render(<SettingsPage />);
    expect(screen.queryByText('View your papers')).not.toBeInTheDocument();
  });

  it('10. loading skeleton shown during auth restore', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: null, loading: true });
    render(<SettingsPage />);
    expect(screen.queryByText('Manage your account')).not.toBeInTheDocument();
  });

  it('11. sign-in prompt shown for unauthenticated users', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: null, loading: false });
    render(<SettingsPage />);
    expect(screen.getByText(/Sign in to manage your settings/i)).toBeInTheDocument();
  });

  it('12. security section shows session info', () => {
    (useAuth as jest.Mock).mockReturnValue({ user: facultyUser, loading: false });
    render(<SettingsPage />);
    expect(screen.getAllByText('Security').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Managed via authentication tokens/i)).toBeInTheDocument();
  });
});
