'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, ClipboardEvent, FormEvent, KeyboardEvent } from 'react';
import { KeyRound } from 'lucide-react';

import { forgotPasswordRequest, verifyResetOtp } from '@/lib/api';
import {
  describeResetError,
  getResetFlowEmail,
  setResetFlowToken,
} from '@/lib/reset-flow';
import { Button } from '@/components/ui/button';
import { AuthPanel, AuthShell, AuthSteps } from '@/components/auth/auth-shell';

const OTP_LENGTH = 6;
const RESEND_COOLDOWN_SECONDS = 60;

function maskEmail(email: string): string {
  const [local, domain] = email.split('@');
  if (!domain) return email;
  const visible = local.slice(0, Math.min(2, local.length));
  return `${visible}${'•'.repeat(Math.max(local.length - visible.length, 1))}@${domain}`;
}

export default function VerifyOtpPage() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [digits, setDigits] = useState<string[]>(Array(OTP_LENGTH).fill(''));
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useState(RESEND_COOLDOWN_SECONDS);
  const inputsRef = useRef<Array<HTMLInputElement | null>>(Array(OTP_LENGTH).fill(null));

  // Flow state lives only in memory: without it (direct visit / refresh) the
  // only safe destination is the start of the reset flow.
  useEffect(() => {
    const flowEmail = getResetFlowEmail();
    if (!flowEmail) {
      router.replace('/forgot-password');
      return;
    }
    setEmail(flowEmail);
  }, [router]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => setCooldown((s) => (s > 0 ? s - 1 : 0)), 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  function updateDigit(index: number, raw: string): void {
    const numeric = raw.replace(/\D/g, '');
    if (!numeric) {
      setDigits((prev) => prev.map((d, i) => (i === index ? '' : d)));
      return;
    }
    setDigits((prev) => {
      const next = [...prev];
      for (let offset = 0; offset < numeric.length && index + offset < OTP_LENGTH; offset += 1) {
        next[index + offset] = numeric[offset];
      }
      const fillIndex = next.findIndex((d) => d === '');
      const focusIndex = fillIndex === -1 ? OTP_LENGTH - 1 : fillIndex;
      inputsRef.current[focusIndex]?.focus();
      return next;
    });
  }

  function handleKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === 'Backspace' && !digits[index] && index > 0) {
      inputsRef.current[index - 1]?.focus();
    }
  }

  function handlePaste(event: ClipboardEvent<HTMLInputElement>): void {
    event.preventDefault();
    const pasted = event.clipboardData.getData('text').replace(/\D/g, '').slice(0, OTP_LENGTH);
    if (!pasted) return;
    const next = Array(OTP_LENGTH).fill('');
    pasted.split('').forEach((char, i) => {
      next[i] = char;
    });
    setDigits(next);
    inputsRef.current[Math.min(pasted.length, OTP_LENGTH - 1)]?.focus();
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting || !email) return;
    setError(null);
    setNotice(null);

    const otp = digits.join('');
    if (otp.length !== OTP_LENGTH) {
      setError(`Enter the ${OTP_LENGTH}-digit verification code.`);
      return;
    }

    setSubmitting(true);
    try {
      const result = await verifyResetOtp(email, otp);
      // The reset token stays in in-memory flow state only — never in the URL
      // or persistent storage, and never mixed with auth tokens.
      setResetFlowToken(result.reset_token);
      router.push('/reset-password');
    } catch (err) {
      const message = describeResetError(err, 'Something went wrong. Please try again.');
      if (message.toLowerCase().includes('too many')) {
        setDigits(Array(OTP_LENGTH).fill(''));
        inputsRef.current[0]?.focus();
      }
      setError(message);
      setSubmitting(false);
    }
  }

  async function handleResend() {
    if (resending || cooldown > 0 || !email) return;
    setError(null);
    setNotice(null);
    setResending(true);
    try {
      await forgotPasswordRequest(email);
      setDigits(Array(OTP_LENGTH).fill(''));
      inputsRef.current[0]?.focus();
      setNotice('A new verification code has been sent.');
      setCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (err) {
      setError(describeResetError(err, 'Something went wrong. Please try again.'));
    } finally {
      setResending(false);
    }
  }

  return (
    <AuthShell>
      <AuthPanel>
          <AuthSteps current={2} />
          <div>
            <p className="text-metadata font-medium uppercase tracking-wide text-text-muted">
              Account recovery
            </p>
            <h1 className="mt-1 text-heading font-semibold tracking-tight text-text-primary">
              Verify OTP
            </h1>
            <p className="mt-2 text-small leading-6 text-text-secondary">
              {email
                ? `A verification code was sent to ${maskEmail(email)}.`
                : 'A verification code was sent to your email.'}
              {' '}The code expires in a few minutes.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="mt-7 space-y-5" noValidate>
            <fieldset className="space-y-2">
              <legend className="text-small font-medium text-text-primary">
                Verification code
              </legend>
              <div className="flex justify-between gap-2" aria-label="6-digit verification code">
                {digits.map((digit, index) => (
                  <input
                    key={index}
                    ref={(el) => {
                      inputsRef.current[index] = el;
                    }}
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={OTP_LENGTH}
                    value={digit}
                    aria-label={`Digit ${index + 1} of ${OTP_LENGTH}`}
                    data-testid={`otp-digit-${index}`}
                    onChange={(event: ChangeEvent<HTMLInputElement>) => updateDigit(index, event.target.value)}
                    onKeyDown={(event) => handleKeyDown(index, event)}
                    onPaste={handlePaste}
                    className="h-12 w-12 rounded-xl border border-white/80 bg-white/65 text-center text-body font-semibold text-text-primary shadow-inner outline-none backdrop-blur-sm transition-all duration-micro focus:border-primary focus:ring-2 focus:ring-primary/20"
                  />
                ))}
              </div>
            </fieldset>

            {error ? (
              <div role="alert" data-testid="otp-error" className="rounded-lg border border-danger/25 bg-danger/5 px-4 py-3 text-small text-danger">
                {error}
              </div>
            ) : null}
            {notice ? (
              <div role="status" data-testid="otp-notice" className="rounded-lg border border-success/25 bg-success/5 px-4 py-3 text-small text-success">
                {notice}
              </div>
            ) : null}

            <Button
              type="submit"
              variant="primary"
              fullWidth
              loading={submitting}
              loadingText="Verifying…"
              data-testid="verify-otp-button"
            >
              <KeyRound className="h-4 w-4" aria-hidden />
              Verify OTP
            </Button>

            <div className="flex items-center justify-between text-small">
              <button
                type="button"
                onClick={handleResend}
                disabled={resending || cooldown > 0}
                data-testid="resend-otp-button"
                aria-disabled={resending || cooldown > 0}
                className="font-medium text-text-secondary transition-colors duration-micro hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
              >
                {cooldown > 0 ? `Resend OTP (${cooldown}s)` : 'Resend OTP'}
              </button>
              <Link
                href="/login"
                data-testid="otp-back-to-login"
                className="font-medium text-text-secondary transition-colors duration-micro hover:text-primary"
              >
                Back to Login
              </Link>
            </div>
          </form>
      </AuthPanel>
    </AuthShell>
  );
}
