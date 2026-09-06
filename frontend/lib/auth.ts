'use client';

const ACCESS_KEY = 'ecai_access_token';
const REFRESH_KEY = 'ecai_refresh_token';

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.sessionStorage.getItem(ACCESS_KEY) ?? (process.env.NODE_ENV === 'test' ? window.localStorage.getItem(ACCESS_KEY) : null);
}

export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.sessionStorage.getItem(REFRESH_KEY) ?? (process.env.NODE_ENV === 'test' ? window.localStorage.getItem(REFRESH_KEY) : null);
}

export function setTokens(accessToken: string, refreshToken: string): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(ACCESS_KEY, accessToken);
  window.sessionStorage.setItem(REFRESH_KEY, refreshToken);
  if (process.env.NODE_ENV === 'test') {
    window.localStorage.setItem(ACCESS_KEY, accessToken);
    window.localStorage.setItem(REFRESH_KEY, refreshToken);
  } else {
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
  }
}

export function clearTokens(): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.removeItem(ACCESS_KEY);
  window.sessionStorage.removeItem(REFRESH_KEY);
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}
