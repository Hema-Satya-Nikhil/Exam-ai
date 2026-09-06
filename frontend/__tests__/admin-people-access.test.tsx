import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import AdminPage from '@/app/admin/page';
import { SidebarNav } from '@/components/layout/sidebar-nav';

jest.mock('@/contexts/auth-context', () => ({
  useAuth: jest.fn(),
}));
import { useAuth } from '@/contexts/auth-context';

jest.mock('@/lib/api', () => ({
  __esModule: true,
  listAdminUsers: jest.fn(),
  getAdminRequests: jest.fn(),
  approveAdminRequest: jest.fn(),
  rejectAdminRequest: jest.fn(),
  removeAdminRole: jest.fn(),
  listPendingFaculty: jest.fn(),
  listAuditLogs: jest.fn(),
  approveFaculty: jest.fn(),
  rejectFaculty: jest.fn(),
  disableUser: jest.fn(),
}));
import {
  listAdminUsers,
  listPendingFaculty,
  listAuditLogs,
  getAdminRequests,
  approveFaculty,
  rejectFaculty,
  disableUser,
} from '@/lib/api';

const PENDING = {
  user_id: 'fac-1', email: 'faculty@example.com', full_name: 'Faculty Example',
  is_active: false, roles: ['faculty'], created_at: null,
};
const ACTIVE = {
  user_id: 'fac-2', email: 'active@example.com', full_name: 'Active User',
  is_active: true, roles: ['faculty'], created_at: '2026-08-29T10:00:00Z',
};
const ADMIN = {
  user_id: 'admin-1', email: 'admin@example.com', full_name: 'Admin Example',
  roles: ['admin'], is_active: true,
};

function adminSession() {
  return { user: ADMIN, login: jest.fn(), register: jest.fn(), logout: jest.fn(), loading: false };
}
function facultySession() {
  return { user: { ...PENDING, is_active: true }, login: jest.fn(), register: jest.fn(), logout: jest.fn(), loading: false };
}
function seed() {
  (listAdminUsers as jest.Mock).mockResolvedValue({ users: [ACTIVE, ADMIN] });
  (getAdminRequests as jest.Mock).mockResolvedValue({ requests: [] });
  (listPendingFaculty as jest.Mock).mockResolvedValue({ users: [PENDING] });
  (listAuditLogs as jest.Mock).mockResolvedValue({
    audit_logs: [
      { id: 'a1', action: 'approve_faculty', entity_type: 'user', actor_user_id: 'admin-1', entity_id: 'fac-1', payload: {}, created_at: '2026-08-29T12:00:00Z' },
    ],
  });
}

describe('Admin People & Access (Phase 6)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    seed();
  });

  it('1. admin header shows People & Access with the subtitle', async () => {
    (useAuth as jest.Mock).mockReturnValue(adminSession());
    render(<AdminPage />);
    await waitFor(() => expect(screen.queryByTestId('admin-loading')).not.toBeInTheDocument());
    expect(screen.getByRole('heading', { name: /People & Access/i })).toBeInTheDocument();
    expect(screen.getByText(/Manage who can access your organization workspace/i)).toBeInTheDocument();
  });

  it('5+6. approve shows Approving… then succeeds and reflects API result', async () => {
    (useAuth as jest.Mock).mockReturnValue(adminSession());
    let resolveApprove: (v: unknown) => void = () => {};
    (approveFaculty as jest.Mock).mockReturnValue(new Promise((r) => { resolveApprove = r; }));
    render(<AdminPage />);
    // loadAll now also fetches admin requests: wait for data before interacting
    await waitFor(() => expect(screen.getByTestId('pending-table')).toBeInTheDocument());
    const approve = screen.getAllByTestId('approve-faculty@example.com')[0];  // table + mobile both render
    fireEvent.click(approve);
    expect((await screen.findAllByTestId('approve-faculty@example.com'))[0]).toHaveTextContent('Approving…');
    resolveApprove({ status: 'approved' });
    expect(await screen.findByTestId('admin-notice')).toHaveTextContent('Faculty member approved.');
  });

  it('7+8. reject shows Rejecting… then reports success', async () => {
    (useAuth as jest.Mock).mockReturnValue(adminSession());
    let resolveReject: (v: unknown) => void = () => {};
    (rejectFaculty as jest.Mock).mockReturnValue(new Promise((r) => { resolveReject = r; }));
    render(<AdminPage />);
    await waitFor(() => expect(screen.getByTestId('pending-table')).toBeInTheDocument());
    const reject = screen.getAllByTestId('reject-faculty@example.com')[0];  // table + mobile both render
    fireEvent.click(reject);
    expect((await screen.findAllByTestId('reject-faculty@example.com'))[0]).toHaveTextContent('Rejecting…');
    resolveReject({ status: 'rejected' });
    expect(await screen.findByTestId('admin-notice')).toHaveTextContent('Request rejected.');
  });

  it('11+12. disable shows Disabling… then succeeds', async () => {
    (useAuth as jest.Mock).mockReturnValue(adminSession());
    let resolveDisable: (v: unknown) => void = () => {};
    (disableUser as jest.Mock).mockReturnValue(new Promise((r) => { resolveDisable = r; }));
    render(<AdminPage />);
    fireEvent.click(await screen.findByTestId('tab-users'));
    await waitFor(() => expect(screen.queryByTestId('admin-loading')).not.toBeInTheDocument());
    const disable = screen.getAllByTestId('disable-active@example.com')[0];  // table + mobile both render
    fireEvent.click(disable);
    expect((await screen.findAllByTestId('disable-active@example.com'))[0]).toHaveTextContent('Disabling…');
    resolveDisable({ status: 'disabled' });
    expect(await screen.findByTestId('admin-notice')).toHaveTextContent('Faculty access disabled.');
  });

  it('13. disabled faculty are excluded from the active list', async () => {
    (useAuth as jest.Mock).mockReturnValue(adminSession());
    (listAdminUsers as jest.Mock).mockResolvedValue({
      users: [{ ...ACTIVE, is_active: false, email: 'disabled@example.com' }, ADMIN],
    });
    (getAdminRequests as jest.Mock).mockResolvedValue({ requests: [] });
    render(<AdminPage />);
    fireEvent.click(await screen.findByTestId('tab-users'));
    await waitFor(() => expect(screen.queryByTestId('admin-loading')).not.toBeInTheDocument());
    expect(screen.queryByTestId('user-row-disabled@example.com')).not.toBeInTheDocument();
  });

  it('17. admin guard shows the session-checking loading state', () => {
    (useAuth as jest.Mock).mockReturnValue({ ...adminSession(), user: null, loading: true });
    render(<AdminPage />);
    expect(screen.getByText(/Checking your session/i)).toBeInTheDocument();
    expect(screen.queryByTestId('admin-denied')).not.toBeInTheDocument();
  });

  it('18. unauthorized faculty sees the deny screen', () => {
    (useAuth as jest.Mock).mockReturnValue(facultySession());
    render(<AdminPage />);
    expect(screen.getByTestId('admin-denied')).toBeInTheDocument();
    expect(screen.getByText('Admin access required')).toBeInTheDocument();
  });

  it('15+16. sidebar shows ADMIN items only for admins, never for faculty', () => {
    (useAuth as jest.Mock).mockReturnValue(adminSession());
    const { unmount } = render(<SidebarNav pathname="/admin" />);
    expect(screen.getByText('People & Access')).toBeInTheDocument();
    expect(screen.getByText('Audit')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    unmount();

    (useAuth as jest.Mock).mockReturnValue(facultySession());
    render(<SidebarNav pathname="/dashboard" />);
    expect(screen.queryByText('People & Access')).not.toBeInTheDocument();
    expect(screen.queryByText('Audit')).not.toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('19. mobile pending cards render with distinct mobile test ids', async () => {
    (useAuth as jest.Mock).mockReturnValue(adminSession());
    render(<AdminPage />);
    expect(await screen.findByTestId('pending-table-mobile')).toBeInTheDocument();
    expect(screen.getByTestId('pending-card-faculty@example.com')).toBeInTheDocument();
    expect(screen.getByTestId('approve-faculty@example.com')).toBeInTheDocument();
    expect(screen.getByTestId('approve-faculty@example.com-mobile')).toBeInTheDocument();
  });

  it('20. a busy action never issues a duplicate request on rapid re-click', async () => {
    (useAuth as jest.Mock).mockReturnValue(adminSession());
    let resolveApprove: (v: unknown) => void = () => {};
    (approveFaculty as jest.Mock).mockReturnValue(new Promise((r) => { resolveApprove = r; }));
    render(<AdminPage />);
    // loadAll now also fetches admin requests: wait for data before interacting
    await waitFor(() => expect(screen.getByTestId('pending-table')).toBeInTheDocument());
    const approve = screen.getAllByTestId('approve-faculty@example.com')[0];  // table + mobile both render
    fireEvent.click(approve);
    fireEvent.click(approve); // second click while busy must be ignored
    resolveApprove({ status: 'approved' });
    await waitFor(() => expect(approveFaculty).toHaveBeenCalledTimes(1));
  });
});

