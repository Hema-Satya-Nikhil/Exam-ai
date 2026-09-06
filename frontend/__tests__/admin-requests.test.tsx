import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import LoginPage from '@/app/login/page';
import AdminPage from '@/app/admin/page';

// ---------------------------------------------------------------------------
// Shared mocks
// ---------------------------------------------------------------------------

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn() }),
  usePathname: () => '/',
}));

jest.mock('@/lib/api', () => ({
  __esModule: true,
  loginRequest: jest.fn(),
  registerFaculty: jest.fn(),
  getCurrentUser: jest.fn(),
  logoutRequest: jest.fn(),
  listAdminUsers: jest.fn(),
  listPendingFaculty: jest.fn(),
  listAuditLogs: jest.fn(),
  getAdminRequests: jest.fn(),
  approveFaculty: jest.fn(),
  rejectFaculty: jest.fn(),
  disableUser: jest.fn(),
  approveAdminRequest: jest.fn(),
  rejectAdminRequest: jest.fn(),
  removeAdminRole: jest.fn(),
}));

jest.mock('@/contexts/auth-context', () => ({
  useAuth: jest.fn(),
}));
import { useAuth } from '@/contexts/auth-context';
import {
  registerFaculty,
  listAdminUsers,
  listPendingFaculty,
  listAuditLogs,
  getAdminRequests,
  approveAdminRequest,
  rejectAdminRequest,
  removeAdminRole,
} from '@/lib/api';

const MAIN_ADMIN = {
  user_id: 'admin-1',
  email: 'main.admin@test.com',
  full_name: 'Main Admin',
  is_active: true,
  is_primary_admin: true,
  roles: ['admin'],
  created_at: null,
};

const SECONDARY_ADMIN = {
  user_id: 'admin-2',
  email: 'second.admin@test.com',
  full_name: 'Secondary Admin',
  is_active: true,
  is_primary_admin: false,
  roles: ['admin'],
  created_at: null,
};

const FACULTY_USER = {
  user_id: 'fac-1',
  email: 'faculty@test.com',
  full_name: 'Plain Faculty',
  is_active: true,
  is_primary_admin: false,
  roles: ['faculty'],
  created_at: null,
};

const PENDING_REQUEST = {
  request_id: 'req-1',
  requester_id: 'app-1',
  requester_name: 'Admin Applicant',
  requester_email: 'applicant@test.com',
  requester_is_active: false,
  requested_role: 'admin',
  status: 'pending',
  requested_at: '2026-09-05T00:00:00Z',
  reviewed_at: null,
  reviewer: null,
  review_reason: null,
};

function seedAdminApi(users: Array<Record<string, unknown>>, requests: Array<Record<string, unknown>> = []) {
  (listAdminUsers as jest.Mock).mockResolvedValue({ users });
  (listPendingFaculty as jest.Mock).mockResolvedValue({ users: [] });
  (listAuditLogs as jest.Mock).mockResolvedValue({ audit_logs: [] });
  (getAdminRequests as jest.Mock).mockResolvedValue({ requests });
}

function sessionAs(user: Record<string, unknown>) {
  return {
    user,
    loading: false,
    login: jest.fn(),
    register: jest.fn(),
    logout: jest.fn(),
  };
}

// ---------------------------------------------------------------------------
// Registration â€” Request Admin access
// ---------------------------------------------------------------------------

describe('Registration â€” Request Admin access', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useAuth as jest.Mock).mockImplementation(() => ({
      user: null,
      loading: false,
      login: jest.fn(),
      register: registerFaculty,
      logout: jest.fn(),
    }));
  });

  function openRegister() {
    render(<LoginPage />);
    fireEvent.click(screen.getByTestId('toggle-auth-mode'));
  }

  function fillAndSubmit() {
    fireEvent.change(screen.getByPlaceholderText('name@department.edu'), {
      target: { value: 'applicant@test.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Jane Doe'), { target: { value: 'Applicant' } });
    fireEvent.change(screen.getByPlaceholderText('Your password'), { target: { value: 'Passw0rd!' } });
    fireEvent.change(screen.getByPlaceholderText('Re-type your password'), {
      target: { value: 'Passw0rd!' },
    });
    fireEvent.click(screen.getByTestId('auth-submit'));
  }

  it('renders the Request Admin option with the approval helper text', () => {
    openRegister();
    expect(screen.getByTestId('request-admin-option')).toBeInTheDocument();
    expect(screen.getByTestId('request-admin-checkbox')).not.toBeChecked();
    expect(screen.getByText(/approval from an existing administrator/i)).toBeInTheDocument();
  });

  it('sends request_admin=true and shows the pending-admin message', async () => {
    (registerFaculty as jest.Mock).mockResolvedValue({
      user_id: 'u1',
      email: 'applicant@test.com',
      status: 'pending',
      admin_request_status: 'pending',
    });
    openRegister();
    fireEvent.change(screen.getByPlaceholderText('name@department.edu'), {
      target: { value: 'applicant@test.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Jane Doe'), { target: { value: 'Applicant' } });
    fireEvent.change(screen.getByPlaceholderText('Your password'), { target: { value: 'Passw0rd!' } });
    fireEvent.change(screen.getByPlaceholderText('Re-type your password'), {
      target: { value: 'Passw0rd!' },
    });
    fireEvent.click(screen.getByTestId('request-admin-checkbox'));
    fireEvent.click(screen.getByTestId('auth-submit'));

    await waitFor(() => expect(registerFaculty).toHaveBeenCalledTimes(1));
    const payload = (registerFaculty as jest.Mock).mock.calls[0][0];
    expect(payload.requestAdmin).toBe(true);
    await waitFor(() => {
      expect(
        screen.getByText(/Admin access request is waiting for administrator approval/i)
      ).toBeInTheDocument();
    });
    // Never claims the user IS an admin now.
    expect(screen.getByRole('status').textContent).not.toMatch(/you are now an admin/i);
  });

  it('sends request_admin=false for a normal faculty registration', async () => {
    (registerFaculty as jest.Mock).mockResolvedValue({
      user_id: 'u2',
      email: 'faculty@test.com',
      status: 'pending',
      admin_request_status: null,
    });
    openRegister();
    fillAndSubmit();

    await waitFor(() => expect(registerFaculty).toHaveBeenCalledTimes(1));
    const payload = (registerFaculty as jest.Mock).mock.calls[0][0];
    expect(payload.requestAdmin).toBe(false);
    await waitFor(() => {
      expect(screen.getByText(/faculty account is pending admin approval/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Admin access request is waiting/i)).not.toBeInTheDocument();
  });

  it('reflects the checkbox state when toggled back to Faculty', () => {
    openRegister();
    const checkbox = screen.getByTestId('request-admin-checkbox');
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
    fireEvent.click(checkbox);
    expect(checkbox).not.toBeChecked();
  });
});

// ---------------------------------------------------------------------------
// People & Access â€” Admin Requests UI + Main Admin display
// ---------------------------------------------------------------------------

describe('People & Access â€” Admin Requests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    seedAdminApi([MAIN_ADMIN, SECONDARY_ADMIN, FACULTY_USER], [PENDING_REQUEST]);
  });

  function openRequestsTab(asUser: Record<string, unknown>) {
    (useAuth as jest.Mock).mockReturnValue(sessionAs(asUser));
    render(<AdminPage />);
    fireEvent.click(screen.getByTestId('tab-requests'));
  }

  it('renders the pending admin request card', async () => {
    openRequestsTab(MAIN_ADMIN);
    await waitFor(() => {
      expect(screen.getByTestId('admin-requests-list')).toBeInTheDocument();
    });
    expect(screen.getByTestId('admin-request-applicant@test.com')).toBeInTheDocument();
    expect(screen.getByText('Admin Applicant')).toBeInTheDocument();
    expect(screen.getByText('applicant@test.com')).toBeInTheDocument();
  });

  it('shows the empty state when there are no requests', async () => {
    seedAdminApi([MAIN_ADMIN], []);
    openRequestsTab(MAIN_ADMIN);
    await waitFor(() => {
      expect(screen.getByTestId('admin-requests-empty')).toBeInTheDocument();
    });
    expect(screen.getByText('No admin requests')).toBeInTheDocument();
  });

  it('approves a request and refreshes the lists', async () => {
    (approveAdminRequest as jest.Mock).mockResolvedValue({ ...PENDING_REQUEST, status: 'approved' });
    openRequestsTab(MAIN_ADMIN);
    await waitFor(() => expect(screen.getByTestId('admin-requests-list')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('approve-request-applicant@test.com'));

    await waitFor(() => expect(approveAdminRequest).toHaveBeenCalledWith('req-1'));
    await waitFor(() => expect(getAdminRequests).toHaveBeenCalledTimes(2)); // initial + refresh
    expect(await screen.findByTestId('admin-notice')).toHaveTextContent('Admin access approved.');
  });

  it('rejects a request and passes the optional reason', async () => {
    (rejectAdminRequest as jest.Mock).mockResolvedValue({ ...PENDING_REQUEST, status: 'rejected' });
    openRequestsTab(MAIN_ADMIN);
    await waitFor(() => expect(screen.getByTestId('admin-requests-list')).toBeInTheDocument());

    fireEvent.change(screen.getByTestId('reject-reason-applicant@test.com'), {
      target: { value: 'Insufficient seniority' },
    });
    fireEvent.click(screen.getByTestId('reject-request-applicant@test.com'));

    await waitFor(() => expect(rejectAdminRequest).toHaveBeenCalledWith('req-1', 'Insufficient seniority'));
    await waitFor(() => expect(screen.getByTestId('admin-notice')).toHaveTextContent('Admin access rejected.'));
  });

  it('shows an error state when approval fails', async () => {
    (approveAdminRequest as jest.Mock).mockRejectedValue(new Error('Request failed with status 409'));
    openRequestsTab(MAIN_ADMIN);
    await waitFor(() => expect(screen.getByTestId('admin-requests-list')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('approve-request-applicant@test.com'));
    await waitFor(() => expect(screen.getByTestId('admin-error')).toBeInTheDocument());
  });

  it('identifies the Main Admin and protects it from removal/disable UI', async () => {
    seedAdminApi([MAIN_ADMIN, SECONDARY_ADMIN, FACULTY_USER], []);
    openRequestsTab(MAIN_ADMIN);
    fireEvent.click(screen.getByTestId('tab-users'));
    await waitFor(() => expect(screen.getByTestId('users-table')).toBeInTheDocument());

    expect(screen.getAllByTestId('role-main-admin-main.admin@test.com')[0]).toHaveTextContent('Main Admin');
    expect(screen.getAllByTestId('protected-main-admin-main.admin@test.com')[0]).toHaveTextContent(
      'Protected Main Admin'
    );
    // No remove/disable actions for the Main Admin row.
    expect(screen.queryByTestId('remove-admin-main.admin@test.com')).not.toBeInTheDocument();
    expect(screen.queryByTestId('disable-main.admin@test.com')).not.toBeInTheDocument();
  });

  it('shows the remove-admin action for a secondary admin when actor is Main Admin', async () => {
    seedAdminApi([MAIN_ADMIN, SECONDARY_ADMIN, FACULTY_USER], []);
    openRequestsTab(MAIN_ADMIN);
    fireEvent.click(screen.getByTestId('tab-users'));
    await waitFor(() => expect(screen.getByTestId('users-table')).toBeInTheDocument());

    expect(screen.getAllByTestId('remove-admin-second.admin@test.com').length).toBeGreaterThan(0);
    // Faculty keeps the normal disable action.
    expect(screen.getAllByTestId('disable-faculty@test.com')[0]).toBeInTheDocument();
  });

  it('hides remove-admin for a secondary-admin actor', async () => {
    seedAdminApi([MAIN_ADMIN, SECONDARY_ADMIN, FACULTY_USER], []);
    openRequestsTab(SECONDARY_ADMIN);
    fireEvent.click(screen.getByTestId('tab-users'));
    await waitFor(() => expect(screen.getByTestId('users-table')).toBeInTheDocument());

    expect(screen.getAllByTestId('role-main-admin-main.admin@test.com')[0]).toBeInTheDocument();
    expect(screen.queryAllByTestId('remove-admin-second.admin@test.com').length).toBe(0);
    expect(screen.queryAllByTestId('remove-admin-main.admin@test.com').length).toBe(0);
  });

  it('removes admin access after confirmation and refreshes', async () => {
    seedAdminApi([MAIN_ADMIN, SECONDARY_ADMIN, FACULTY_USER], []);
    (removeAdminRole as jest.Mock).mockResolvedValue({
      message: 'Admin access removed.',
      user_id: 'admin-2',
    });
    openRequestsTab(MAIN_ADMIN);
    fireEvent.click(screen.getByTestId('tab-users'));
    await waitFor(() => expect(screen.getByTestId('users-table')).toBeInTheDocument());

    fireEvent.click(screen.getAllByTestId('remove-admin-second.admin@test.com')[0]);

    await waitFor(() => expect(removeAdminRole).toHaveBeenCalledWith('admin-2'));
    await waitFor(() => expect(getAdminRequests).toHaveBeenCalledTimes(2));
    expect(await screen.findByTestId('admin-notice')).toHaveTextContent('Admin access removed.');
  });
});





