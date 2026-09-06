import { render, screen, waitFor, fireEvent } from '@testing-library/react';

import AdminPage from '@/app/admin/page';

// Mock the auth context so AdminPage sees an authenticated ADMIN.
jest.mock('@/contexts/auth-context', () => ({
  useAuth: jest.fn(),
}));
import { useAuth } from '@/contexts/auth-context';

// Mock the API client — we only need the admin surface here.
jest.mock('@/lib/api', () => ({
  __esModule: true,
  listAdminUsers: jest.fn(),
  listPendingFaculty: jest.fn(),
  listAuditLogs: jest.fn(),
  approveFaculty: jest.fn(),
  rejectFaculty: jest.fn(),
  disableUser: jest.fn(),
  getAdminRequests: jest.fn(),
  approveAdminRequest: jest.fn(),
  rejectAdminRequest: jest.fn(),
  removeAdminRole: jest.fn(),
}));
import {
  listAdminUsers,
  listPendingFaculty,
  listAuditLogs,
  approveFaculty,
  rejectFaculty,
  disableUser,
  getAdminRequests,
} from '@/lib/api';

const PENDING_USER = {
  user_id: 'fac-1',
  email: 'faculty@example.com',
  full_name: 'Faculty Example',
  is_active: false,
  roles: ['faculty'],
  created_at: null,
};

function mockAdminSession() {
  return {
    user: {
      user_id: 'admin-1',
      email: 'admin@example.com',
      full_name: 'Admin Example',
      roles: ['admin'],
      is_active: true,
    },
    login: jest.fn(),
    register: jest.fn(),
    logout: jest.fn(),
    loading: false,
  };
}

function seedApi() {
  (listAdminUsers as jest.Mock).mockResolvedValue({ users: [] });
  (listPendingFaculty as jest.Mock).mockResolvedValue({ users: [PENDING_USER] });
  (getAdminRequests as jest.Mock).mockResolvedValue({ requests: [] });
  (listAuditLogs as jest.Mock).mockResolvedValue({
    audit_logs: [
      {
        id: 'a1',
        action: 'approve_faculty',
        entity_type: 'user',
        actor_user_id: 'admin-1',
        entity_id: 'fac-1',
        payload: {},
        created_at: null,
      },
    ],
  });
  (approveFaculty as jest.Mock).mockResolvedValue({ status: 'approved' });
}

describe('AdminPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    seedApi();
  });

  it('shows the pending faculty table after loading and renders the approve action', async () => {
    (useAuth as jest.Mock).mockReturnValue(mockAdminSession());
    render(<AdminPage />);

    // Loading state first
    expect(screen.getByTestId('admin-loading')).toBeInTheDocument();

    await waitFor(() => expect(screen.getByTestId('pending-table')).toBeInTheDocument());
    expect(screen.getByTestId('pending-row-faculty@example.com')).toBeInTheDocument();
    // The approve button should be wired to the pending user
    expect(screen.getByTestId('approve-faculty@example.com')).toBeInTheDocument();
  });

    it('calls approveFaculty with the user id and shows a notice on success', async () => {
        (useAuth as jest.Mock).mockReturnValue(mockAdminSession());
    render(<AdminPage />);

    await waitFor(() => screen.getByTestId('pending-table'));
    const approve = screen.getAllByTestId('approve-faculty@example.com')[0];
    fireEvent.click(approve);

    await waitFor(() => expect(approveFaculty).toHaveBeenCalledWith('fac-1'));
    // The approval triggers a re-fetch (loadAll) — wait until all async work
    // has settled so there are no outstanding state updates after teardown.
    expect(await screen.findByTestId('admin-notice')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByTestId('admin-loading')).not.toBeInTheDocument());
  });

  it('renders the audit table with the recorded admin action', async () => {
    (useAuth as jest.Mock).mockReturnValue(mockAdminSession());
    render(<AdminPage />);

    const auditTab = await screen.findByTestId('tab-audit');
    fireEvent.click(auditTab);

    expect(await screen.findByTestId('audit-table')).toBeInTheDocument();
    expect(screen.getByTestId('audit-row-approve_faculty')).toBeInTheDocument();
  });

  it('denies access for non-admin users', () => {
    (useAuth as jest.Mock).mockReturnValue({
      user: {
        user_id: 'fac-1',
        email: 'faculty@example.com',
        full_name: 'Faculty Example',
        roles: ['faculty'],
        is_active: true,
      },
      login: jest.fn(),
      register: jest.fn(),
      logout: jest.fn(),
      loading: false,
    });
    render(<AdminPage />);
    expect(screen.getByTestId('admin-denied')).toBeInTheDocument();
  });

  it('shows an empty state when there are no pending faculty registrations', async () => {
    (useAuth as jest.Mock).mockReturnValue(mockAdminSession());
    (listPendingFaculty as jest.Mock).mockResolvedValue({ users: [] });
    render(<AdminPage />);

    expect(await screen.findByTestId('pending-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('pending-table')).not.toBeInTheDocument();
  });

  it('shows a meaningful error when the admin API fails', async () => {
    (useAuth as jest.Mock).mockReturnValue(mockAdminSession());
    (listAdminUsers as jest.Mock).mockRejectedValue(new Error('Backend unreachable'));
    render(<AdminPage />);

    expect(await screen.findByTestId('admin-error')).toHaveTextContent('Backend unreachable');
    expect(screen.getByTestId('admin-refresh')).toBeInTheDocument();
  });

  it('calls rejectFaculty with the user id and disables both buttons while processing', async () => {
    (useAuth as jest.Mock).mockReturnValue(mockAdminSession());
    let resolveReject: (v: unknown) => void = () => {};
    (rejectFaculty as jest.Mock).mockReturnValue(
      new Promise((resolve) => { resolveReject = resolve; })
    );
        render(<AdminPage />);

    await waitFor(() => screen.getByTestId('pending-table'));
    const reject = screen.getAllByTestId('reject-faculty@example.com')[0];
    fireEvent.click(reject);

    // Duplicate-action prevention: both actions for that user are disabled
    // while the request is in flight.
    expect(screen.getByTestId('reject-faculty@example.com')).toBeDisabled();
    expect(screen.getByTestId('approve-faculty@example.com')).toBeDisabled();

    resolveReject({ status: 'rejected' });
    expect(await screen.findByTestId('admin-notice')).toBeInTheDocument();
    await waitFor(() => expect(rejectFaculty).toHaveBeenCalledWith('fac-1'));
    await waitFor(() => expect(screen.queryByTestId('admin-loading')).not.toBeInTheDocument());
  });

  it('renders the active users table with roles, status and a disable action for faculty', async () => {
    (useAuth as jest.Mock).mockReturnValue(mockAdminSession());
    (listAdminUsers as jest.Mock).mockResolvedValue({
      users: [
        { ...PENDING_USER, user_id: 'fac-2', email: 'active@example.com', is_active: true },
        { user_id: 'admin-1', email: 'admin@example.com', full_name: 'Admin Example', is_active: true, roles: ['admin'], created_at: null },
      ],
    });
    render(<AdminPage />);

    fireEvent.click(await screen.findByTestId('tab-users'));
    const row = await screen.findByTestId('user-row-active@example.com');
    expect(row).toHaveTextContent('faculty');
    expect(row).toHaveTextContent('Active');
        expect(screen.getAllByTestId('disable-active@example.com')[0]).toBeInTheDocument();
    // Admins are never shown a disable button (self-disable protection in UX).
    expect(screen.queryByTestId('disable-admin@example.com')).not.toBeInTheDocument();
  });

  it('calls disableUser with the user id and refreshes the list', async () => {
    (useAuth as jest.Mock).mockReturnValue(mockAdminSession());
    (listAdminUsers as jest.Mock).mockResolvedValue({
      users: [{ ...PENDING_USER, user_id: 'fac-2', email: 'active@example.com', is_active: true }],
    });
    (disableUser as jest.Mock).mockResolvedValue({ status: 'disabled' });
    render(<AdminPage />);

    fireEvent.click(await screen.findByTestId('tab-users'));
    fireEvent.click(screen.getAllByTestId('disable-active@example.com')[0]);

    await waitFor(() => expect(disableUser).toHaveBeenCalledWith('fac-2'));
    expect(await screen.findByTestId('admin-notice')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByTestId('admin-loading')).not.toBeInTheDocument());
  });
});
