'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import type { FormEvent } from 'react';
import { CheckCircle2, Eye, EyeOff } from 'lucide-react';
import { BrandLogo } from '@/components/brand/brand-logo';

import { useAuth } from '@/contexts/auth-context';
import { Button } from '@/components/ui/button';
import { AuthPanel } from '@/components/auth/auth-shell';

export default function LoginPage() {
  const { login, register } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [requestAdmin, setRequestAdmin] = useState(false);

  /**
   * Presentation-only mapping of backend messages to faculty-friendly copy.
   * The backend already returns safe, non-technical messages; this normalises
   * the common cases so the wording is consistent. Anything unrecognised is
   * shown as-is — no state is invented.
   */
  function friendlyAuthError(message: string): string {
    const m = message.toLowerCase();
    if (m.includes('awaiting') || m.includes('pending approval')) {
      return 'Your account is awaiting administrator approval.';
    }
    if (m.includes('deactivated') || m.includes('disabled') || m.includes('inactive')) {
      return 'Your account has been deactivated.';
    }
    if (
      m.includes('invalid') ||
      m.includes('credential') ||
      m.includes('incorrect') ||
      m.includes('wrong password')
    ) {
      return 'Email or password is incorrect.';
    }
    if (m.includes('fetch') || m.includes('network') || m.includes('connect')) {
      return 'Unable to connect. Please try again.';
    }
    return message;
  }

  function toggle(): void {
    setMode(mode === 'login' ? 'register' : 'login');
    setError(null);
    setSuccess(null);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    // Guard against duplicate submission (double click, Enter-key race) while
    // a sign-in/registration request is already in flight.
    if (submitting) return;
    setError(null);
    setSuccess(null);
    if (!email.trim() || !password) {
      setError('Enter your email and password to continue.');
      return;
    }
    if (mode === 'register' && password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    setSubmitting(true);
    try {
      if (mode === 'register') {
        const result = await register({
          email: email.trim(),
          full_name: fullName.trim(),
          password,
          requestAdmin
        });
        // Backend is authoritative: requestAdmin only creates a PENDING admin
        // request — it never grants ADMIN. Reflect the returned state.
        if (result.admin_request_status === 'pending') {
          setSuccess(
            'Your account has been created and your Admin access request is waiting for administrator approval.'
          );
        } else {
          setSuccess(
            'Your faculty account is pending admin approval. You will be able to sign in once an administrator approves it.'
          );
        }
        setRequestAdmin(false);
        setMode('login');
      } else {
        // Backend role is authoritative: admins land on the admin console,
        // faculty on the dashboard. Never trust client-side role state here —
        // /admin re-verifies via the backend on every API call.
        const me = await login(email.trim(), password);
        // Defensive: an unexpected login payload still routes to the faculty
        // dashboard rather than crashing the submission handler.
        const roles: string[] = Array.isArray(me?.roles) ? me.roles : [];
        router.push(roles.includes('admin') ? '/admin' : '/dashboard');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Submission failed. Please try again.';
      setError(friendlyAuthError(message));
    } finally {
      setSubmitting(false);
    }
  }

    return (
    <main className="relative flex min-h-screen overflow-hidden bg-background text-text-primary">
      <div aria-hidden="true" className="pointer-events-none absolute -left-24 top-[-8rem] h-80 w-80 rounded-full bg-primary-soft/40 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute bottom-[-10rem] right-[-6rem] h-96 w-96 rounded-full bg-info-soft/40 blur-3xl" />
      {/* Brand panel — desktop only */}
      <aside
        aria-hidden
        className="relative z-10 hidden w-[42%] flex-col justify-between border-r border-white/70 bg-white/40 p-12 backdrop-blur-xl lg:flex"
      >
        <div className="animate-fade-in">
          <BrandLogo className="h-32 w-32" priority />
          <h2 className="mt-10 max-w-sm text-heading font-semibold leading-tight tracking-tight text-text-primary">
            Create validated exam papers faster.
          </h2>
          <ul className="mt-10 space-y-5">
            {[
              'Syllabus-aware question generation',
              'Structured parts, marks, and Bloom levels',
              'Review, regenerate, and lock every question',
            ].map((item) => (
              <li key={item} className="flex items-start gap-3 text-body text-text-secondary">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-metadata text-text-muted">
          Faculty accounts require administrator approval before first sign-in.
        </p>
      </aside>

      {/* Form column */}
      <section className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="mb-3 flex justify-center lg:hidden">
            <BrandLogo className="h-24 w-24" priority />
          </div>
          <AuthPanel>
          <div>
            <p className="text-metadata font-medium uppercase tracking-wide text-text-muted">
              Department workspace
            </p>
            <h1 className="mt-1 text-heading font-semibold tracking-tight text-text-primary">
              {mode === 'login' ? 'Sign in to ExamCraft' : 'Register as faculty'}
            </h1>
            <p className="mt-2 text-small leading-6 text-text-secondary">
              Create your question paper — configure the syllabus, paper structure, question
              distribution, and evaluation criteria before generation.
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
                className="w-full rounded-xl border border-white/80 bg-white/65 px-4 py-3 text-body text-text-primary shadow-inner outline-none backdrop-blur-sm transition-all duration-micro placeholder:text-text-muted focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
            </label>

            {mode === 'register' ? (
              <label className="block space-y-2">
                <span className="text-small font-medium text-text-primary">Full name</span>
                <input
                  type="text"
                  autoComplete="name"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  placeholder="Jane Doe"
                  className="w-full rounded-xl border border-white/80 bg-white/65 px-4 py-3 text-body text-text-primary shadow-inner outline-none backdrop-blur-sm transition-all duration-micro placeholder:text-text-muted focus:border-primary focus:ring-2 focus:ring-primary/20"
                  required
                />
              </label>
            ) : null}

            <label className="block space-y-2">
              <span className="text-small font-medium text-text-primary">Password</span>
              <span className="relative block">
                <input
                  type={showPassword ? 'text' : 'password'}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Your password"
                  className="w-full rounded-xl border border-white/80 bg-white/65 px-4 py-3 pr-12 text-body text-text-primary shadow-inner outline-none backdrop-blur-sm transition-all duration-micro placeholder:text-text-muted focus:border-primary focus:ring-2 focus:ring-primary/20"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                  className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-text-muted transition-colors duration-micro hover:text-text-primary"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
                </button>
              </span>
            </label>

            {mode === 'register' ? (
              <label className="block space-y-2">
                <span className="text-small font-medium text-text-primary">Confirm password</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(event) => setConfirm(event.target.value)}
                  placeholder="Re-type your password"
                  className="w-full rounded-[8px] border border-line bg-surface px-4 py-3 text-body text-text-primary outline-none transition-colors duration-micro placeholder:text-text-muted focus:border-primary"
                />
              </label>
            ) : null}

            {mode === 'register' ? (
              <label
                htmlFor="request-admin-access"
                className="flex items-start gap-3 rounded-lg border border-line bg-surface-elevated px-4 py-3"
                data-testid="request-admin-option"
              >
                <input
                  id="request-admin-access"
                  type="checkbox"
                  checked={requestAdmin}
                  onChange={(event) => setRequestAdmin(event.target.checked)}
                  data-testid="request-admin-checkbox"
                  className="mt-0.5 h-4 w-4 rounded-[4px] border-line text-primary accent-[rgb(var(--primary))]"
                />
                <span>
                  <span className="block text-small font-medium text-text-primary">
                    Request Admin access
                  </span>
                  <span className="mt-0.5 block text-metadata text-text-secondary">
                    Admin access requires approval from an existing administrator.
                  </span>
                </span>
              </label>
            ) : null}

            {mode === 'login' ? (
              <div className="flex justify-end">
                <Link
                  href="/forgot-password"
                  data-testid="forgot-password-link"
                  className="font-medium text-text-secondary transition-colors duration-micro hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                >
                  Forgot password?
                </Link>
              </div>
            ) : null}

            {error ? (
              <div role="alert" className="rounded-lg border border-danger/25 bg-danger/5 px-4 py-3 text-small text-danger">
                {error}
              </div>
            ) : null}
            {success ? (
              <div role="status" className="rounded-lg border border-success/25 bg-success/5 px-4 py-3 text-small text-success">
                {success}
              </div>
            ) : null}

            <Button
              type="submit"
              variant="primary"
              fullWidth
              loading={submitting}
              loadingText="Working…"
              data-testid="auth-submit"
            >
              {mode === 'login' ? 'Sign in' : 'Register'}
            </Button>
          </form>

          <div className="mt-6 flex items-center justify-between text-small">
            <Link href="/" className="font-medium text-text-secondary transition-colors duration-micro hover:text-primary">
              Back to home
            </Link>
            <button
              type="button"
              onClick={toggle}
              data-testid="toggle-auth-mode"
              className="font-medium text-text-secondary transition-colors duration-micro hover:text-primary"
            >
              {mode === 'login' ? 'Need an account?' : 'Already have an account?'}
            </button>
            </div>
            </AuthPanel>
          </div>
      </section>
    </main>
  );
}
