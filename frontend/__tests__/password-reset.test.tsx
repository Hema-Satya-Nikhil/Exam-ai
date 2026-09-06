import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

import ForgotPasswordPage from '@/app/forgot-password/page';
import VerifyOtpPage from '@/app/verify-otp/page';
import ResetPasswordPage from '@/app/reset-password/page';
import LoginPage from '@/app/login/page';
import {
  startResetFlow,
  getResetFlowToken,
  getResetFlowEmail,
  clearResetFlow,
  setResetFlowToken,
} from '@/lib/reset-flow';

const mockPush = jest.fn();
const mockReplace = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
}));

jest.mock('@/lib/api', () => ({
  __esModule: true,
  forgotPasswordRequest: jest.fn(),
  verifyResetOtp: jest.fn(),
  resetPassword: jest.fn(),
  loginRequest: jest.fn(),
  registerFaculty: jest.fn(),
  getCurrentUser: jest.fn(),
  logoutRequest: jest.fn(),
}));

jest.mock('@/contexts/auth-context', () => ({
  useAuth: jest.fn(() => ({
    user: null,
    loading: false,
    login: jest.fn(),
    register: jest.fn(),
    logout: jest.fn(),
  })),
}));
import { useAuth } from '@/contexts/auth-context';

import {
  forgotPasswordRequest,
  verifyResetOtp,
  resetPassword,
} from '@/lib/api';

function apiErr(status: number, detail: string): Error {
  return new Error(JSON.stringify({ detail }), { cause: undefined }) as Error;
}

describe('Login page — Forgot Password link', () => {
  it('renders the Forgot Password link pointing at /forgot-password (login mode only)', () => {
    render(<LoginPage />);
    const link = screen.getByTestId('forgot-password-link');
    expect(link).toHaveAttribute('href', '/forgot-password');
  });
});

describe('Reset flow state (in-memory, never persisted)', () => {
  beforeEach(() => clearResetFlow());

  it('stores the email and transitions through the steps', () => {
    startResetFlow('a@b.edu');
    expect(getResetFlowEmail()).toBe('a@b.edu');
    expect(getResetFlowToken()).toBeNull();
    setResetFlowToken('tok-123');
    expect(getResetFlowToken()).toBe('tok-123');
    clearResetFlow();
    expect(getResetFlowEmail()).toBeNull();
    expect(getResetFlowToken()).toBeNull();
  });
});

describe('ForgotPasswordPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clearResetFlow();
  });

  it('renders email input, Send OTP button and Back to Login', () => {
    render(<ForgotPasswordPage />);
    expect(screen.getByText('Forgot Password')).toBeInTheDocument();
    expect(screen.getByTestId('forgot-email')).toBeInTheDocument();
    expect(screen.getByTestId('send-otp-button')).toBeInTheDocument();
    expect(screen.getByTestId('forgot-back-to-login')).toHaveAttribute('href', '/login');
  });

  it('rejects an invalid email format without calling the API', async () => {
    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByTestId('forgot-email'), {
      target: { value: 'not-an-email' },
    });
    fireEvent.click(screen.getByTestId('send-otp-button'));
    await waitFor(() =>
      expect(screen.getByTestId('forgot-error')).toHaveTextContent(/valid email/i)
    );
    expect(forgotPasswordRequest).not.toHaveBeenCalled();
  });

  it('navigates to /verify-otp and stores the email on success', async () => {
    (forgotPasswordRequest as jest.Mock).mockResolvedValue({
      message: 'If an account exists for this email, a password reset OTP has been sent.',
    });
    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByTestId('forgot-email'), {
      target: { value: 'Faculty@Example.edu' },
    });
    fireEvent.click(screen.getByTestId('send-otp-button'));
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/verify-otp'));
    expect(forgotPasswordRequest).toHaveBeenCalledWith('faculty@example.edu');
    expect(getResetFlowEmail()).toBe('faculty@example.edu');
  });

  it('maps a 429 cooldown response to its friendly detail', async () => {
    (forgotPasswordRequest as jest.Mock).mockRejectedValue(
      apiErr(429, 'Too many requests. Please wait a minute before requesting another code.')
    );
    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByTestId('forgot-email'), {
      target: { value: 'a@b.edu' },
    });
    fireEvent.click(screen.getByTestId('send-otp-button'));
    await waitFor(() =>
      expect(screen.getByTestId('forgot-error')).toHaveTextContent(/too many requests/i)
    );
  });

  it('shows a generic fallback for non-detail server errors', async () => {
    (forgotPasswordRequest as jest.Mock).mockRejectedValue(
      new Error('Request failed with status 500')
    );
    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByTestId('forgot-email'), { target: { value: 'a@b.edu' } });
    fireEvent.click(screen.getByTestId('send-otp-button'));
    await waitFor(() =>
      expect(screen.getByTestId('forgot-error')).toHaveTextContent(/something went wrong/i)
    );
  });
});

describe('VerifyOtpPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    clearResetFlow();
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  function fillOtp(otp: string): void {
    otp.split('').forEach((char, i) => {
      fireEvent.change(screen.getByTestId(`otp-digit-${i}`), { target: { value: char } });
    });
  }

  it('redirects back to /forgot-password when flow state is missing', () => {
    render(<VerifyOtpPage />);
    expect(mockReplace).toHaveBeenCalledWith('/forgot-password');
  });

  it('renders six numeric OTP inputs with a masked email', () => {
    startResetFlow('faculty@example.edu');
    render(<VerifyOtpPage />);
    for (let i = 0; i < 6; i += 1) {
      expect(screen.getByTestId(`otp-digit-${i}`)).toHaveAttribute('inputmode', 'numeric');
    }
    expect(screen.getByText(/was sent to/)).toHaveTextContent('fa•••••@example.edu');
  });

  it('strips non-numeric input and reports incomplete codes', async () => {
    startResetFlow('a@b.edu');
    render(<VerifyOtpPage />);
    fireEvent.change(screen.getByTestId('otp-digit-0'), { target: { value: '1a2' } });
    // "1a2" → digits [1,2] numeric-only, auto-advanced
    expect(screen.getByTestId('otp-digit-0')).toHaveValue('1');
    expect(screen.getByTestId('otp-digit-1')).toHaveValue('2');
    fireEvent.click(screen.getByTestId('verify-otp-button'));
    await waitFor(() =>
      expect(screen.getByTestId('otp-error')).toHaveTextContent(/6-digit/i)
    );
    expect(verifyResetOtp).not.toHaveBeenCalled();
  });

  it('supports pasting a full 6-digit code', () => {
    startResetFlow('a@b.edu');
    render(<VerifyOtpPage />);
    fireEvent.paste(screen.getByTestId('otp-digit-0'), {
      clipboardData: { getData: () => '654321' },
    });
    for (let i = 0; i < 6; i += 1) {
      expect(screen.getByTestId(`otp-digit-${i}`)).toHaveValue(String('654321'[i]));
    }
  });

  it('shows backend detail on invalid OTP without navigating', async () => {
    startResetFlow('a@b.edu');
    (verifyResetOtp as jest.Mock).mockRejectedValue(apiErr(400, 'Incorrect verification code.'));
    render(<VerifyOtpPage />);
    fillOtp('000000');
    fireEvent.click(screen.getByTestId('verify-otp-button'));
    await waitFor(() =>
      expect(screen.getByTestId('otp-error')).toHaveTextContent(/incorrect/i)
    );
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('on success stores the reset token in flow state only and navigates', async () => {
    startResetFlow('a@b.edu');
    (verifyResetOtp as jest.Mock).mockResolvedValue({ reset_token: 'tok-abc' });
    render(<VerifyOtpPage />);
    fillOtp('123456');
    fireEvent.click(screen.getByTestId('verify-otp-button'));
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/reset-password'));
    expect(getResetFlowToken()).toBe('tok-abc');
    // never in the URL
    expect(mockPush).not.toHaveBeenCalledWith(expect.stringContaining('tok'));
    clearResetFlow();
  });

  it('disables resend during cooldown, then resend calls forgotPasswordRequest', async () => {
    startResetFlow('a@b.edu');
    (forgotPasswordRequest as jest.Mock).mockResolvedValue({ message: 'ok' });
    render(<VerifyOtpPage />);
    const resend = screen.getByTestId('resend-otp-button');
    expect(resend).toBeDisabled();
    expect(resend).toHaveTextContent(/60s/);
    act(() => {
      jest.advanceTimersByTime(61_000);
    });
    expect(resend).toBeEnabled();
    await act(async () => {
      fireEvent.click(resend);
    });
    expect(forgotPasswordRequest).toHaveBeenCalledWith('a@b.edu');
    expect(screen.getByTestId('otp-notice')).toHaveTextContent(/new verification code/i);
    expect(resend).toBeDisabled(); // cooldown restarted
  });

  it('maps resend 429 to a friendly cooldown message', async () => {
    startResetFlow('a@b.edu');
    (forgotPasswordRequest as jest.Mock).mockRejectedValue(
      apiErr(429, 'Too many requests. Please wait a minute before requesting another code.')
    );
    render(<VerifyOtpPage />);
    const resend = screen.getByTestId('resend-otp-button');
    act(() => {
      jest.advanceTimersByTime(61_000);
    });
    expect(resend).toBeEnabled();
    await act(async () => {
      fireEvent.click(resend);
    });
    await waitFor(() =>
      expect(screen.getByTestId('otp-error')).toHaveTextContent(/too many requests/i)
    );
  });
});

describe('ResetPasswordPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clearResetFlow();
  });

  it('redirects to /forgot-password when no reset token exists and never submits', () => {
    render(<ResetPasswordPage />);
    expect(mockReplace).toHaveBeenCalledWith('/forgot-password');
    expect(screen.queryByTestId('reset-password-button')).not.toBeInTheDocument();
  });

  it('rejects a short password before calling the API', async () => {
    startResetFlow('a@b.edu');
    setResetFlowToken('tok-1');
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByTestId('new-password'), { target: { value: 'short1!' } });
    fireEvent.change(screen.getByTestId('confirm-password'), { target: { value: 'short1!' } });
    fireEvent.click(screen.getByTestId('reset-password-button'));
    await waitFor(() =>
      expect(screen.getByTestId('reset-error')).toHaveTextContent(/at least 8/i)
    );
    expect(resetPassword).not.toHaveBeenCalled();
  });

  it('rejects mismatched passwords', async () => {
    startResetFlow('a@b.edu');
    setResetFlowToken('tok-1');
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByTestId('new-password'), { target: { value: 'LongEnough1!' } });
    fireEvent.change(screen.getByTestId('confirm-password'), { target: { value: 'Different1!' } });
    fireEvent.click(screen.getByTestId('reset-password-button'));
    await waitFor(() =>
      expect(screen.getByTestId('reset-error')).toHaveTextContent(/do not match/i)
    );
    expect(resetPassword).not.toHaveBeenCalled();
  });

  it('resets the password, clears the flow, and shows the success state', async () => {
    startResetFlow('a@b.edu');
    setResetFlowToken('tok-1');
    (resetPassword as jest.Mock).mockResolvedValue({ message: 'Password reset successfully.' });
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByTestId('new-password'), { target: { value: 'NewPass123!' } });
    fireEvent.change(screen.getByTestId('confirm-password'), { target: { value: 'NewPass123!' } });
    fireEvent.click(screen.getByTestId('reset-password-button'));
    await waitFor(() =>
      expect(screen.getByTestId('reset-success')).toBeInTheDocument()
    );
    expect(resetPassword).toHaveBeenCalledWith('tok-1', 'NewPass123!');
    expect(screen.getByTestId('reset-success')).toHaveTextContent(
      'Your password has been reset successfully.'
    );
    expect(getResetFlowToken()).toBeNull();
    expect(getResetFlowEmail()).toBeNull();
  });

  it('maps an expired/used token response to the backend detail', async () => {
    startResetFlow('a@b.edu');
    setResetFlowToken('tok-dead');
    (resetPassword as jest.Mock).mockRejectedValue(
      apiErr(400, 'This password reset request is invalid or already used.')
    );
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByTestId('new-password'), { target: { value: 'NewPass123!' } });
    fireEvent.change(screen.getByTestId('confirm-password'), { target: { value: 'NewPass123!' } });
    fireEvent.click(screen.getByTestId('reset-password-button'));
    await waitFor(() =>
      expect(screen.getByTestId('reset-error')).toHaveTextContent(/invalid or already used/i)
    );
  });
});


