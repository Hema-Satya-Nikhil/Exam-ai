'use client';

/**
 * In-memory state for the active password-reset flow.
 *
 * Deliberately separate from AuthContext (which owns login tokens): the reset
 * token is a narrow, short-lived, single-purpose authorization and must never
 * mix with access/refresh tokens, URLs, or persistent storage. Being in-memory
 * only means a page refresh safely drops the flow and the pages redirect back
 * to /forgot-password.
 */

export type PasswordResetStep = 'email' | 'otp' | 'reset';

export interface PasswordResetFlow {
  email: string;
  resetToken?: string;
  step: PasswordResetStep;
}

let flow: PasswordResetFlow | null = null;

export function startResetFlow(email: string): void {
  flow = { email, step: 'otp' };
}

export function setResetFlowToken(resetToken: string): void {
  if (flow) {
    flow = { ...flow, resetToken, step: 'reset' };
  }
}

export function getResetFlowEmail(): string | null {
  return flow?.email ?? null;
}

export function getResetFlowToken(): string | null {
  return flow?.resetToken ?? null;
}

export function clearResetFlow(): void {
  flow = null;
}

/**
 * Extract a safe, user-facing message from an ApiError. The backend returns
 * FastAPI `{"detail": "..."}` bodies (apiFetch surfaces the raw text); this
 * unwraps the detail and falls back to friendly copy for network/unknown
 * failures. Never exposes stack traces or internal details.
 */
export function describeResetError(error: unknown, fallback: string): string {
  const message = error instanceof Error ? error.message : '';
  try {
    const parsed = JSON.parse(message) as { detail?: unknown };
    if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
      return parsed.detail;
    }
  } catch {
    // Not a JSON body — fall through.
  }
  if (message && !message.startsWith('Request failed')) {
    return message;
  }
  return fallback;
}

