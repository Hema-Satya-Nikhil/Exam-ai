require('@testing-library/jest-dom');

// App Router navigation hooks are unavailable outside a mounted Next.js app.
// Pages under test now render the AppShell, which uses usePathname.
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn()
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams()
}));
