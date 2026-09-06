import { clearTokens, getAccessToken, getRefreshToken, setTokens } from '../lib/auth';

describe('client authentication session storage', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
  });

  it('stores active credentials in session storage and clears legacy persistent tokens', () => {
    window.localStorage.setItem('ecai_access_token', 'legacy-access');
    window.localStorage.setItem('ecai_refresh_token', 'legacy-refresh');

    setTokens('access', 'refresh');

    expect(window.sessionStorage.getItem('ecai_access_token')).toBe('access');
    expect(window.sessionStorage.getItem('ecai_refresh_token')).toBe('refresh');
    // Jest keeps a localStorage mirror for existing API test fixtures.
    expect(window.localStorage.getItem('ecai_access_token')).toBe('access');
    expect(window.localStorage.getItem('ecai_refresh_token')).toBe('refresh');
    expect(getAccessToken()).toBe('access');
    expect(getRefreshToken()).toBe('refresh');
  });

  it('clears credentials from both session and legacy storage on logout', () => {
    window.localStorage.setItem('ecai_access_token', 'legacy-access');
    window.localStorage.setItem('ecai_refresh_token', 'legacy-refresh');
    window.sessionStorage.setItem('ecai_access_token', 'access');
    window.sessionStorage.setItem('ecai_refresh_token', 'refresh');

    clearTokens();

    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });
});
