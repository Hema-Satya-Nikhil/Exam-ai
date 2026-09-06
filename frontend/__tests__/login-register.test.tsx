import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import LoginPage from '@/app/login/page';

// next/navigation is used only for router.push → mock it.
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
import { registerFaculty, loginRequest } from '@/lib/api';

describe('LoginPage', () => {
  const mockRegister = jest.fn(() =>
    Promise.resolve({ user_id: 'new-1', email: 'new@example.com', status: 'pending' })
  );
  const mockLogin = jest.fn(() => Promise.resolve({ id: 'u1', roles: ['faculty'] as string[] }));

  beforeEach(() => {
    jest.clearAllMocks();
    (useAuth as jest.Mock).mockImplementation(() => ({
      user: null,
      loading: false,
      login: mockLogin,
      register: mockRegister,
      logout: jest.fn(),
    }));
  });

    it('renders the login form by default', () => {
    render(<LoginPage />);
    expect(screen.getByText('Sign in to ExamCraft')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('name@department.edu')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Your password')).toBeInTheDocument();
    expect(screen.getByText('Sign in')).toBeInTheDocument();
  });

  it('toggles to the registration form, showing the full-name and confirm fields', () => {
    render(<LoginPage />);
    fireEvent.click(screen.getByTestId('toggle-auth-mode'));

    expect(screen.getByText('Register as faculty')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Re-type your password')).toBeInTheDocument();
    expect(screen.getByText('Register')).toBeInTheDocument();
  });

  it('blocks submission when passwords do not match', () => {
    render(<LoginPage />);
    fireEvent.click(screen.getByTestId('toggle-auth-mode'));

    fireEvent.change(screen.getByPlaceholderText('name@department.edu'), { target: { value: 'new@example.com' } });
    fireEvent.change(screen.getByPlaceholderText('Jane Doe'), { target: { value: 'Jane Doe' } });
    fireEvent.change(screen.getByPlaceholderText('Your password'), { target: { value: 'pass-one' } });
    fireEvent.change(screen.getByPlaceholderText('Re-type your password'), { target: { value: 'pass-two' } });

    fireEvent.click(screen.getByText('Register'));

    expect(screen.getByText('Passwords do not match.')).toBeInTheDocument();
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it('submits the registration payload and shows a pending-approval notice', async () => {
    render(<LoginPage />);
    fireEvent.click(screen.getByTestId('toggle-auth-mode'));

    fireEvent.change(screen.getByPlaceholderText('name@department.edu'), { target: { value: 'new@example.com' } });
    fireEvent.change(screen.getByPlaceholderText('Jane Doe'), { target: { value: 'Jane Doe' } });
    fireEvent.change(screen.getByPlaceholderText('Your password'), { target: { value: 'Pass123!' } });
    fireEvent.change(screen.getByPlaceholderText('Re-type your password'), { target: { value: 'Pass123!' } });

    fireEvent.click(screen.getByText('Register'));

        await waitFor(() =>
      expect(mockRegister).toHaveBeenCalledWith({
        email: 'new@example.com',
        full_name: 'Jane Doe',
        password: 'Pass123!',
        requestAdmin: false,
      })
    );
    expect(
      await screen.findByText(/pending admin approval/i)
    ).toBeInTheDocument();
  });

  it('signs in with valid credentials and navigates to the dashboard', async () => {
    render(<LoginPage />);
    fireEvent.change(screen.getByPlaceholderText('name@department.edu'), { target: { value: 'admin@example.com' } });
    fireEvent.change(screen.getByPlaceholderText('Your password'), { target: { value: 'Pass123!' } });
    fireEvent.click(screen.getByText('Sign in'));

        await waitFor(() => expect(mockLogin).toHaveBeenCalledWith('admin@example.com', 'Pass123!'));
  });

  it('issues exactly ONE login call and one navigation per sign-in, and blocks re-submit while working', async () => {
    // Resolve only after the test releases the deferred promise, so the
    // "Working..." state is observable and duplicate clicks are exercised.
    let release!: () => void;
    const gate = new Promise<{ id: string; roles: string[] }>((resolve) => {
      release = () => resolve({ id: 'u1', roles: ['faculty'] });
    });
    mockLogin.mockImplementation(() => gate);

    render(<LoginPage />);
    fireEvent.change(screen.getByPlaceholderText('name@department.edu'), { target: { value: 'admin@example.com' } });
    fireEvent.change(screen.getByPlaceholderText('Your password'), { target: { value: 'Pass123!' } });
    fireEvent.click(screen.getByText('Sign in'));

    // Button enters the busy state and disables duplicate submission.
    const busyButton = await screen.findByText('Working…');
    expect(busyButton.closest('button')).toBeDisabled();

    fireEvent.click(busyButton.closest('button') as HTMLButtonElement);
    fireEvent.submit(busyButton.closest('form') as HTMLFormElement);

    release();
    await waitFor(() => expect(mockLogin).toHaveBeenCalledTimes(1));
    expect(mockPush).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith('/dashboard');
  });
});
