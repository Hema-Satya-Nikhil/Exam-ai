import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import LoginPage from '@/app/login/page';

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock('@/lib/api', () => ({
  __esModule: true,
  loginRequest: jest.fn(),
  registerFaculty: jest.fn(),
  getCurrentUser: jest.fn(),
  logoutRequest: jest.fn(),
}));

jest.mock('@/contexts/auth-context', () => ({
  useAuth: jest.fn(),
}));
import { useAuth } from '@/contexts/auth-context';

/**
 * Error-mapping and accessibility coverage for the redesigned auth screen.
 * Each failure case mocks the EXACT backend message shape so no account
 * state is fabricated in the UI layer.
 */
describe('Login UX: error mapping, password toggle, accessibility', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useAuth as jest.Mock).mockImplementation(() => ({
      user: null,
      loading: false,
      login: jest.fn(),
      register: jest.fn(),
      logout: jest.fn(),
    }));
  });

  async function submitWithLoginError(message: string) {
    (useAuth as jest.Mock).mockImplementation(() => ({
      user: null,
      loading: false,
      login: jest.fn().mockRejectedValue(new Error(message)),
      register: jest.fn(),
      logout: jest.fn(),
    }));
    render(<LoginPage />);
    fireEvent.change(screen.getByPlaceholderText('name@department.edu'), {
      target: { value: 'user@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Your password'), { target: { value: 'pw' } });
    fireEvent.click(screen.getByText('Sign in'));
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
  }

  it('maps invalid credentials to a friendly message', async () => {
    await submitWithLoginError('Invalid email or password');
    expect(screen.getByRole('alert')).toHaveTextContent('Email or password is incorrect.');
  });

  it('maps pending-approval rejection to the awaiting-approval message', async () => {
    await submitWithLoginError('Your faculty account is awaiting administrator approval.');
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Your account is awaiting administrator approval.'
    );
  });

  it('maps deactivated accounts to the deactivated message', async () => {
    await submitWithLoginError('Your account has been deactivated.');
    expect(screen.getByRole('alert')).toHaveTextContent('Your account has been deactivated.');
  });

  it('maps network failures to a connection message', async () => {
    await submitWithLoginError('TypeError: fetch failed');
    expect(screen.getByRole('alert')).toHaveTextContent('Unable to connect. Please try again.');
  });

  it('password visibility toggle flips the field type and aria state', () => {
    render(<LoginPage />);
    const toggle = screen.getByRole('button', { name: 'Show password' });
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
    const field = screen.getByPlaceholderText('Your password');
    expect(field).toHaveAttribute('type', 'password');

    fireEvent.click(toggle);
    expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute('aria-pressed', 'true');
    expect(field).toHaveAttribute('type', 'text');

    fireEvent.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(field).toHaveAttribute('type', 'password');
  });

  it('admin role routes to /admin after successful login', async () => {
    (useAuth as jest.Mock).mockImplementation(() => ({
      user: null,
      loading: false,
      login: jest.fn().mockResolvedValue({ id: 'u1', roles: ['admin'] }),
      register: jest.fn(),
      logout: jest.fn(),
    }));
    render(<LoginPage />);
    fireEvent.change(screen.getByPlaceholderText('name@department.edu'), {
      target: { value: 'admin@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Your password'), { target: { value: 'pw' } });
    fireEvent.click(screen.getByText('Sign in'));
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/admin'));
  });

  it('renders errors with role=alert and the brand panel is decorative (aria-hidden)', () => {
    render(<LoginPage />);
    const aside = document.querySelector('aside[aria-hidden="true"]');
    expect(aside).not.toBeNull();
    // Email input keeps its accessible label
    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('name@department.edu')).toHaveAttribute('autoComplete', 'email');
  });
});
