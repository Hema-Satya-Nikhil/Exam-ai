'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { getCurrentUser, loginRequest, logoutRequest, registerFaculty } from '@/lib/api';
import type { CurrentUser, RegisterOptions, RegisterResponse } from '@/lib/api';
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from '@/lib/auth';

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<CurrentUser>;
  register: (options: RegisterOptions) => Promise<RegisterResponse>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession(): Promise<void> {
      // Persistent localStorage tokens from older releases must never restore
      // an account in a new browser session.
      window.localStorage.removeItem('ecai_access_token');
      window.localStorage.removeItem('ecai_refresh_token');
      if (!getAccessToken() && !getRefreshToken()) {
        setLoading(false);
        return;
      }
      try {
        const me = await getCurrentUser();
        if (!cancelled) setUser(me);
      } catch {
        clearTokens();
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, []);

    const login = useCallback(async (email: string, password: string) => {
    const tokens = await loginRequest(email, password);
    setTokens(tokens.access_token, tokens.refresh_token);
      try {
        const me = await getCurrentUser();
        setUser(me);
        return me;
      } catch (error) {
        clearTokens();
        setUser(null);
        throw error;
      }
    }, []);

  // Faculty self-registration: creates an inactive (pending) account. No tokens
  // are issued — the user must wait for admin approval before signing in.
  const register = useCallback(
    async (options: RegisterOptions) => {
      const result = await registerFaculty(options);
      return result;
    },
    []
  );

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        await logoutRequest(refreshToken);
      } catch {
        // ignore logout network errors; tokens are cleared regardless
      }
    }
    clearTokens();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
