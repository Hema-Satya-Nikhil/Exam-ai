'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Eye, EyeOff, ShieldCheck } from 'lucide-react';

import { resetPassword } from '@/lib/api';
import { clearResetFlow, describeResetError, getResetFlowToken } from '@/lib/reset-flow';
import { Button } from '@/components/ui/button';
import { AuthPanel, AuthShell, AuthSteps } from '@/components/auth/auth-shell';

export default function ResetPasswordPage() {
  const router = useRouter();
  const [hasToken, setHasToken] = useState(false);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // The reset token exists only in in-memory flow state. Without it there is
  // nothing to submit — render nothing and go back to the start of the flow.
  useEffect(() => {
    if (!getResetFlowToken()) {
      router.replace('/forgot-password');
      return;
    }
    setHasToken(true);
  }, [router]);

  if (!hasToken) {
    return <AuthShell><div aria-busy="true" /></AuthShell>;
  }

  function toggleVisibility(): void {
    setShowPassword((v) => !v);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return; // duplicate-submission guard
    setError(null);

    const resetToken = getResetFlowToken();
    if (!resetToken) {
      // No valid authorization — never submit anything.
      router.replace('/forgot-password');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      await resetPassword(resetToken, password);
      // The flow (and its token) is dead after a successful reset.
      clearResetFlow();
      setPassword('');
      setConfirm('');
      setSuccess('Your password has been reset successfully.');
    } catch (err) {
      setError(describeResetError(err, 'Something went wrong. Please try again.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell>
      <AuthPanel>
          <AuthSteps current={3} />
          {success ? (
            <div className="text-center" data-testid="reset-success">
              <ShieldCheck className="mx-auto h-10 w-10 text-success" aria-hidden />
              <h1 className="mt-3 text-heading font-semibold tracking-tight text-text-primary">
                Password reset
              </h1>
              <p role="status" className="mt-2 text-small leading-6 text-text-secondary">
                {success}
              </p>
              <div className="mt-7">
                <Link href="/login" data-testid="success-back-to-login">
                  <Button variant="primary" fullWidth>
                    Back to Login
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <>
              <div>
                <p className="text-metadata font-medium uppercase tracking-wide text-text-muted">
                  Account recovery
                </p>
                <h1 className="mt-1 text-heading font-semibold tracking-tight text-text-primary">
                  Reset Password
                </h1>
                <p className="mt-2 text-small leading-6 text-text-secondary">
                  Choose a new password for your account. It must be at least 8
                  characters long.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="mt-7 space-y-5" noValidate>
                <label className="block space-y-2">
                  <span className="text-small font-medium text-text-primary">New Password</span>
                  <span className="relative block">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="new-password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      placeholder="At least 8 characters"
                      data-testid="new-password"
                      className="w-full rounded-xl border border-white/80 bg-white/65 px-4 py-3 pr-12 text-body text-text-primary shadow-inner outline-none backdrop-blur-sm transition-all duration-micro placeholder:text-text-muted focus:border-primary focus:ring-2 focus:ring-primary/20"
                    />
                    <button
                      type="button"
                      onClick={toggleVisibility}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      aria-pressed={showPassword}
                      className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-text-muted transition-colors duration-micro hover:text-text-primary"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
                    </button>
                  </span>
                </label>

                <label className="block space-y-2">
                  <span className="text-small font-medium text-text-primary">Confirm Password</span>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    value={confirm}
                    onChange={(event) => setConfirm(event.target.value)}
                    placeholder="Re-type your new password"
                    data-testid="confirm-password"
                    className="w-full rounded-xl border border-white/80 bg-white/65 px-4 py-3 text-body text-text-primary shadow-inner outline-none backdrop-blur-sm transition-all duration-micro placeholder:text-text-muted focus:border-primary focus:ring-2 focus:ring-primary/20"
                  />
                </label>

                {error ? (
                  <div role="alert" data-testid="reset-error" className="rounded-lg border border-danger/25 bg-danger/5 px-4 py-3 text-small text-danger">
                    {error}
                  </div>
                ) : null}

                <Button
                  type="submit"
                  variant="primary"
                  fullWidth
                  loading={submitting}
                  loadingText="Resetting…"
                  data-testid="reset-password-button"
                >
                  Reset Password
                </Button>
              </form>

              <div className="mt-6 flex justify-start text-small">
                <Link
                  href="/login"
                  data-testid="reset-back-to-login"
                  className="font-medium text-text-secondary transition-colors duration-micro hover:text-primary"
                >
                  Back to Login
                </Link>
              </div>
            </>
          )}
      </AuthPanel>
    </AuthShell>
  );
}
