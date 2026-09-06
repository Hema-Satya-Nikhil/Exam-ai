'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import type { FormEvent } from 'react';
import { Mail } from 'lucide-react';

import { forgotPasswordRequest } from '@/lib/api';
import { describeResetError, startResetFlow } from '@/lib/reset-flow';
import { Button } from '@/components/ui/button';
import { AuthPanel, AuthShell, AuthSteps } from '@/components/auth/auth-shell';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return; // duplicate-submission guard
    setError(null);

    const normalized = email.trim().toLowerCase();
    if (!normalized) {
      setError('Enter your registered email address.');
      return;
    }
    if (!EMAIL_PATTERN.test(normalized)) {
      setError('Enter a valid email address.');
      return;
    }

    setSubmitting(true);
    try {
      const result = await forgotPasswordRequest(normalized);
      // Backend response is deliberately generic — shown as-is, no existence
      // inference. The non-sensitive email carries into the next step via
      // in-memory flow state (never the URL).
      startResetFlow(normalized);
      router.push('/verify-otp');
      void result;
    } catch (err) {
      setError(describeResetError(err, 'Something went wrong. Please try again.'));
      setSubmitting(false);
    }
  }

  return (
    <AuthShell>
      <AuthPanel>
          <AuthSteps current={1} />
          <div>
            <p className="text-metadata font-medium uppercase tracking-wide text-text-muted">
              Account recovery
            </p>
            <h1 className="mt-1 text-heading font-semibold tracking-tight text-text-primary">
              Forgot Password
            </h1>
            <p className="mt-2 text-small leading-6 text-text-secondary">
              Enter your registered email address and we will send you a one-time
              verification code to reset your password.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="mt-7 space-y-5" noValidate>
            <label className="block space-y-2">
              <span className="text-small font-medium text-text-primary">Email</span>
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="name@department.edu"
                data-testid="forgot-email"
                className="w-full rounded-xl border border-white/80 bg-white/65 px-4 py-3 text-body text-text-primary shadow-inner outline-none backdrop-blur-sm transition-all duration-micro placeholder:text-text-muted focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
            </label>

            {error ? (
              <div role="alert" data-testid="forgot-error" className="rounded-lg border border-danger/25 bg-danger/5 px-4 py-3 text-small text-danger">
                {error}
              </div>
            ) : null}

            <Button
              type="submit"
              variant="primary"
              fullWidth
              loading={submitting}
              loadingText="Sending…"
              data-testid="send-otp-button"
            >
              <Mail className="h-4 w-4" aria-hidden />
              Send OTP
            </Button>
          </form>

          <div className="mt-6 flex justify-start text-small">
            <Link
              href="/login"
              data-testid="forgot-back-to-login"
              className="font-medium text-text-secondary transition-colors duration-micro hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
            >
              Back to Login
            </Link>
          </div>
      </AuthPanel>
    </AuthShell>
  );
}
