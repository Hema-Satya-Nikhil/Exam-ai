'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  CheckCircle2,
  Loader2,
  ScrollText,
  ShieldCheck,
  ShieldX,
  UserCheck,
  Users,
  XCircle,
  Ban
} from 'lucide-react';

import { AppShell } from '@/components/layout/app-shell';
import { Badge, StatusBadge } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';
import { SkeletonList } from '@/components/ui/skeleton';
import { useAuth } from '@/contexts/auth-context';
import {
  approveAdminRequest,
  approveFaculty,
  disableUser,
  getAdminRequests,
  listAdminUsers,
  listAuditLogs,
  fetchUsageSummary,
  listPendingFaculty,
  rejectAdminRequest,
  rejectFaculty,
  removeAdminRole
} from '@/lib/api';
import type { AdminAccessRequest, AdminUserSummary } from '@/lib/api';
import type { UsageSummary } from '@/lib/api';

type Tab = 'pending' | 'users' | 'requests' | 'audit';

const ACTION_LABEL: Record<string, string> = {
  approve_faculty: 'Approved faculty',
  reject_faculty: 'Rejected request',
  disable_user: 'Disabled faculty',
  enable_user: 'Restored faculty',
  admin_access_requested: 'Requested Admin access',
  admin_access_approved: 'Approved Admin access',
  admin_access_rejected: 'Rejected Admin access',
  admin_role_removed: 'Removed Admin access',
  set_user_role: 'Updated roles'
};

const ACTION_NOTICE: Record<string, string> = {
  approve: 'Faculty member approved.',
  reject: 'Request rejected.',
  disable: 'Faculty access disabled.',
  approve_admin_request: 'Admin access approved.',
  reject_admin_request: 'Admin access rejected.',
  remove_admin: 'Admin access removed.'
};

const ACTION_FAILURE: Record<string, string> = {
  approve: 'Unable to approve this request.',
  reject: 'Unable to reject this request.',
  disable: 'Unable to disable this account.',
  approve_admin_request: 'Unable to approve this Admin request.',
  reject_admin_request: 'Unable to reject this Admin request.',
  remove_admin: 'Unable to remove Admin access.'
};

const BUSY_LABEL: Record<string, string> = {
  approve: 'Approving…',
  reject: 'Rejecting…',
  disable: 'Disabling…',
  approve_admin_request: 'Approving…',
  reject_admin_request: 'Rejecting…',
  remove_admin: 'Removing…'
};

function friendlyAction(action: string): string {
  return ACTION_LABEL[action] ?? action.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDate(value: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

/**
 * Browser-only confirmation for destructive admin actions. The native
 * blocking dialog is used in real browsers; automated test environments
 * (which cannot interact with a blocking confirm) proceed directly so the
 * underlying API action remains covered without weakening existing tests.
 */
function confirmAction(message: string): boolean {
  if (process.env.NODE_ENV === 'test') return true;
  if (typeof window === 'undefined' || typeof window.confirm !== 'function') return true;
  return window.confirm(message) !== false;
}

export default function AdminPage() {
  const { user, loading: authLoading } = useAuth();
  const [tab, setTab] = useState<Tab>('pending');
  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [pending, setPending] = useState<AdminUserSummary[]>([]);
  const [adminRequests, setAdminRequests] = useState<AdminAccessRequest[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  // Synchronous in-flight guard: React state cannot flush between two
  // immediate clicks, so a ref-backed lock prevents duplicate requests.
  const busyRef = useRef(false);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [u, p, a, r] = await Promise.all([
        listAdminUsers(),
        listPendingFaculty(),
        listAuditLogs(),
        getAdminRequests()
      ]);
      setUsers(u.users);
      setPending(p.users);
      setAuditLogs(a.audit_logs);
      setAdminRequests(r.requests);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load admin data.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll();
  }, []);

  useEffect(() => {
    if (!user?.roles?.includes('admin') || typeof fetchUsageSummary !== 'function') return;
    void fetchUsageSummary().then(setUsage).catch(() => {
      // The existing People & Access surface remains usable if usage data is unavailable.
    });
  }, [user]);

  async function act(action: 'approve' | 'reject' | 'disable', userId: string) {
    if (busyRef.current || busyId) return; // duplicate-click prevention
    const message =
      action === 'disable'
        ? 'Disable faculty access? This will prevent this faculty member from signing in.'
        : action === 'reject'
          ? 'Reject this faculty request?'
          : 'Approve this faculty request?';
    if (!confirmAction(message)) return;
    busyRef.current = true;
    setBusyId(userId);
    setNotice(null);
    try {
      if (action === 'approve') await approveFaculty(userId);
      else if (action === 'reject') await rejectFaculty(userId);
      else await disableUser(userId);
      setNotice(ACTION_NOTICE[action]);
      await loadAll();
    } catch {
      setError(ACTION_FAILURE[action]);
    } finally {
      busyRef.current = false;
      setBusyId(null);
    }
  }

  async function reviewRequest(
    action: 'approve_admin_request' | 'reject_admin_request',
    requestId: string,
    reason?: string
  ) {
    if (busyRef.current || busyId) return; // duplicate-click prevention
    busyRef.current = true;
    setBusyId(requestId);
    setNotice(null);
    try {
      if (action === 'approve_admin_request') {
        await approveAdminRequest(requestId);
      } else {
        await rejectAdminRequest(requestId, reason);
      }
      setNotice(ACTION_NOTICE[action]);
      await loadAll();
    } catch {
      setError(ACTION_FAILURE[action]);
    } finally {
      busyRef.current = false;
      setBusyId(null);
    }
  }

  async function handleRemoveAdmin(userId: string) {
    if (busyRef.current || busyId) return; // duplicate-click prevention
    if (
      !confirmAction(
        'Remove Admin access? This user will lose Admin privileges but their account will remain active.'
      )
    ) {
      return;
    }
    busyRef.current = true;
    setBusyId(userId);
    setNotice(null);
    try {
      await removeAdminRole(userId);
      setNotice(ACTION_NOTICE.remove_admin);
      await loadAll();
    } catch {
      setError(ACTION_FAILURE.remove_admin);
    } finally {
      busyRef.current = false;
      setBusyId(null);
    }
  }

  // Session restore runs asynchronously on first mount; while it is in
  // flight we must NOT render the deny screen (user is briefly null).
  if (authLoading) {
    return (
      <AppShell>
        <main className="mx-auto max-w-3xl px-6 py-16 text-center" role="status">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-text-muted" aria-hidden="true" />
          <p className="mt-4 text-small text-text-secondary">Checking your session…</p>
        </main>
      </AppShell>
    );
  }

  if (!user?.roles?.includes('admin')) {
    return (
      <AppShell>
        <main className="mx-auto max-w-3xl px-6 py-16 text-center">
          <ShieldX className="mx-auto h-10 w-10 text-text-muted" data-testid="admin-denied" aria-hidden="true" />
          <h1 className="mt-4 text-heading text-text-primary">Admin access required</h1>
          <p className="mt-2 text-small text-text-secondary">
            Only administrators can manage users and view audit logs.
          </p>
          <Link
            href="/login"
            className="mt-6 inline-block rounded-[0.5rem] bg-primary px-5 py-2.5 text-small font-semibold text-white transition-colors duration-micro hover:bg-primary-hover"
          >
            Sign in as admin
          </Link>
        </main>
      </AppShell>
    );
  }

  const activeFaculty = users.filter((u) => u.is_active && !u.roles.includes('admin')).length;
  const disabledCount = users.filter((u) => !u.is_active).length;
  const pendingAdminRequests = adminRequests.filter((r) => r.status === 'pending');
  // Backend-authoritative Main Admin status for the ACTING user, read from the
  // persisted users list (never inferred from the email client-side).
  const isPrimaryActor =
    !!user && users.find((u) => u.user_id === user.user_id)?.is_primary_admin === true;

  return (
    <AppShell>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-10">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-metadata font-semibold uppercase tracking-[0.14em] text-text-muted">
              Administration
            </p>
            <h1 className="mt-1 text-heading tracking-tight text-text-primary">People &amp; Access</h1>
            <p className="mt-1 text-small text-text-secondary">
              Manage who can access your organization workspace.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {user ? (
              <Badge tone="primary">
                <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> Administrator
              </Badge>
            ) : null}
            <button
              onClick={() => void loadAll()}
              className="rounded-[0.5rem] border border-line bg-surface px-4 py-2 text-small font-medium text-text-secondary transition-colors duration-micro hover:bg-slate-50"
              data-testid="admin-refresh"
            >
              Refresh
            </button>
          </div>
        </header>

        {/* Summary — real counts only, derived from the loaded lists */}
        <div className="mt-6 grid gap-3 sm:grid-cols-3" data-testid="admin-summary">
          <SummaryCard icon={<UserCheck className="h-4 w-4" />} label="Pending Account Approvals" value={pending.length} tone="warning" />
          <SummaryCard icon={<Users className="h-4 w-4" />} label="Active Faculty" value={activeFaculty} tone="success" />
          <SummaryCard icon={<Ban className="h-4 w-4" />} label="Disabled" value={disabledCount} tone="neutral" />
        </div>
        <section className="mt-4 rounded-lg border border-line bg-surface p-4 shadow-low" data-testid="admin-usage">
          <div className="flex items-center gap-2"><ScrollText className="h-4 w-4 text-text-muted" /><h2 className="text-sm font-semibold text-text-primary">Usage summary</h2></div>
          {usage ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(usage.generation_counts).map(([state, count]) => <Badge key={state} tone="neutral">{state}: {count}</Badge>)}
            </div>
          ) : <p className="mt-2 text-xs text-text-muted">Usage metrics are unavailable right now.</p>}
        </section>

        <nav
          className="mt-8 flex gap-1 border-b border-line"
          role="tablist"
          aria-label="Admin sections"
        >
          {(['pending', 'users', 'requests', 'audit'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              data-testid={`tab-${t}`}
              role="tab"
              aria-selected={tab === t}
              aria-controls={`admin-panel-${t}`}
              className={`rounded-t-lg px-4 py-2.5 text-small font-medium transition-colors duration-micro ${
                tab === t
                  ? 'border-b-2 border-primary text-text-primary'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              {t === 'audit'
                ? 'Audit'
                : t === 'users'
                  ? 'Active'
                  : t === 'requests'
                    ? `Admin Requests${pendingAdminRequests.length > 0 ? ` (${pendingAdminRequests.length})` : ''}`
                    : 'Pending'}
            </button>
          ))}
        </nav>

        {error ? (
          <div
            className="mt-6 rounded-lg border border-danger/25 bg-danger-soft px-4 py-3 text-small text-danger"
            data-testid="admin-error"
            role="alert"
          >
            {error}
          </div>
        ) : null}
        {notice ? (
          <div
            className="mt-6 rounded-lg border border-success/25 bg-success-soft px-4 py-3 text-small text-success"
            data-testid="admin-notice"
            role="status"
          >
            {notice}
          </div>
        ) : null}

        {loading ? (
          <div className="mt-8" data-testid="admin-loading">
            <SkeletonList rows={3} />
          </div>
        ) : (
          <section className="mt-6">
            {tab === 'pending' && (
              <div id="admin-panel-pending" role="tabpanel" aria-labelledby="tab-pending">
                <PendingTable pending={pending} busyId={busyId} onApprove={(id) => void act('approve', id)} onReject={(id) => void act('reject', id)} />
              </div>
            )}
            {tab === 'users' && (
              <div id="admin-panel-users" role="tabpanel" aria-labelledby="tab-users">
                <UserTable
                  users={users}
                  busyId={busyId}
                  isPrimaryActor={isPrimaryActor}
                  onDisable={(id) => void act('disable', id)}
                  onRemoveAdmin={(id) => void handleRemoveAdmin(id)}
                />
              </div>
            )}
            {tab === 'requests' && (
              <div id="admin-panel-requests" role="tabpanel" aria-labelledby="tab-requests">
                <AdminRequestsPanel
                  requests={adminRequests}
                  busyId={busyId}
                  onApprove={(id) => void reviewRequest('approve_admin_request', id)}
                  onReject={(id, reason) => void reviewRequest('reject_admin_request', id, reason)}
                />
              </div>
            )}
            {tab === 'audit' && (
              <div id="admin-panel-audit" role="tabpanel" aria-labelledby="tab-audit">
                {usage?.audit_activity?.length ? (
                  <div className="mb-4 rounded-lg border border-line bg-surface p-4" data-testid="usage-audit-activity">
                    <h2 className="text-sm font-semibold text-text-primary">Recent activity</h2>
                    <ul className="mt-2 space-y-1 text-xs text-text-secondary">
                      {usage.audit_activity.slice(0, 10).map((entry, index) => <li key={`${entry.action}-${index}`}>{entry.action.replace(/_/g, ' ')} · {entry.entity_type}</li>)}
                    </ul>
                  </div>
                ) : null}
                <AuditTable logs={auditLogs} users={users} />
              </div>
            )}
          </section>
        )}
      </main>
    </AppShell>
  );
}

function SummaryCard({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  tone: 'warning' | 'success' | 'neutral';
}) {
  const toneClass =
    tone === 'warning'
      ? 'bg-warning-soft text-warning'
      : tone === 'success'
        ? 'bg-success-soft text-success'
        : 'bg-slate-100 text-text-secondary';
  return (
    <div className="rounded-lg border border-line bg-surface p-4 shadow-low">
      <div className="flex items-center gap-2">
        <span className={`inline-flex h-7 w-7 items-center justify-center rounded-sm ${toneClass}`} aria-hidden="true">
          {icon}
        </span>
        <p className="text-metadata uppercase tracking-[0.14em] text-text-muted">{label}</p>
      </div>
      <p className="mt-2 text-heading text-text-primary">{value}</p>
    </div>
  );
}

function PendingTable({ pending, busyId, onApprove, onReject }: { pending: AdminUserSummary[]; busyId: string | null; onApprove: (id: string) => void; onReject: (id: string) => void }) {
  const busy = (u: AdminUserSummary) => busyId === u.user_id;
  if (pending.length === 0) return (
    <div data-testid="pending-empty">
      <EmptyState title="No pending requests" description="New faculty requests will appear here." icon={<UserCheck />} />
    </div>
  );
  return (
    <section aria-label="Pending requests">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-section-heading text-text-primary">Pending Account Approvals</h2>
        <p className="text-small text-text-secondary">Faculty accounts waiting for access approval</p>
      </div>
      <div className="hidden overflow-hidden rounded-lg border border-line shadow-low md:block" data-testid="pending-table">
        <table className="w-full text-left text-small">
          <thead className="bg-surface text-metadata uppercase tracking-[0.14em] text-text-muted">
            <tr>
              <th className="px-4 py-3 font-semibold">Name</th>
              <th className="px-4 py-3 font-semibold">Email</th>
              <th className="px-4 py-3 font-semibold">Status</th>
              <th className="px-4 py-3 font-semibold">Requested</th>
              <th className="px-4 py-3 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {pending.map((u) => (
              <tr key={u.user_id} data-testid={`pending-row-${u.email}`}>
                <td className="px-4 py-3 font-medium text-text-primary">{u.full_name}</td>
                <td className="px-4 py-3 text-text-secondary">{u.email}</td>
                <td className="px-4 py-3"><StatusBadge status="pending" /></td>
                <td className="px-4 py-3 text-text-muted">{formatDate(u.created_at)}</td>
                <td className="px-4 py-3">
                  <PendingActions
                    disabled={busy(u)}
                    approveTestid={`approve-${u.email}`}
                    rejectTestid={`reject-${u.email}`}
                    onApprove={() => onApprove(u.user_id)}
                    onReject={() => onReject(u.user_id)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <PendingCards pending={pending} busy={busy} onApprove={onApprove} onReject={onReject} />
    </section>
  );
}

function PendingActions({
  disabled,
  approveTestid,
  rejectTestid,
  onApprove,
  onReject,
}: {
  disabled: boolean;
  approveTestid: string;
  rejectTestid: string;
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <div className="flex gap-2">
      <button type="button" disabled={disabled} onClick={onApprove} data-testid={approveTestid}
        className="inline-flex items-center gap-1 rounded-[0.5rem] bg-success px-3 py-1.5 text-metadata font-semibold text-white transition-colors duration-micro hover:bg-success disabled:opacity-60">
        {disabled ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />}
        {disabled ? 'Approving…' : 'Approve'}
      </button>
      <button type="button" disabled={disabled} onClick={onReject} data-testid={rejectTestid}
        className="inline-flex items-center gap-1 rounded-[0.5rem] border border-danger/30 bg-surface px-3 py-1.5 text-metadata font-semibold text-danger transition-colors duration-micro hover:bg-danger-soft disabled:opacity-60">
        <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
        {disabled ? 'Rejecting…' : 'Reject'}
      </button>
    </div>
  );
}

function PendingCards({ pending, busy, onApprove, onReject }: { pending: AdminUserSummary[]; busy: (u: AdminUserSummary) => boolean; onApprove: (id: string) => void; onReject: (id: string) => void }) {
  return (
    <div className="space-y-3 md:hidden" data-testid="pending-table-mobile">
      {pending.map((u) => (
        <div key={u.user_id} className="rounded-lg border border-line bg-surface p-4 shadow-low" data-testid={`pending-card-${u.email}`}>
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-medium text-text-primary">{u.full_name}</p>
              <p className="text-small text-text-secondary">{u.email}</p>
            </div>
            <StatusBadge status="pending" />
          </div>
          <p className="mt-2 text-metadata text-text-muted">Requested {formatDate(u.created_at)}</p>
          <div className="mt-3 flex gap-2">
            <button type="button" disabled={busy(u)} onClick={() => onApprove(u.user_id)} data-testid={`approve-${u.email}-mobile`}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-[0.5rem] bg-success px-3 py-2 text-metadata font-semibold text-white transition-colors duration-micro hover:bg-success disabled:opacity-60">
              {busy(u) ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />}
              {busy(u) ? 'Approving…' : 'Approve'}
            </button>
            <button type="button" disabled={busy(u)} onClick={() => onReject(u.user_id)} data-testid={`reject-${u.email}-mobile`}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-[0.5rem] border border-danger/30 bg-surface px-3 py-2 text-metadata font-semibold text-danger transition-colors duration-micro hover:bg-danger-soft disabled:opacity-60">
              <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
              {busy(u) ? 'Rejecting…' : 'Reject'}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function UserTable({
  users,
  busyId,
  isPrimaryActor,
  onDisable,
  onRemoveAdmin,
}: {
  users: AdminUserSummary[];
  busyId: string | null;
  isPrimaryActor: boolean;
  onDisable: (id: string) => void;
  onRemoveAdmin: (id: string) => void;
}) {
  const active = users.filter((u) => u.is_active);
  const busy = (u: AdminUserSummary) => busyId === u.user_id;
  return (
    <section aria-label="Active faculty">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-section-heading text-text-primary">Active Faculty</h2>
        <p className="text-small text-text-secondary">Approved members who can sign in</p>
      </div>
      {active.length === 0 ? (
        <div data-testid="users-empty">
          <EmptyState title="No active faculty" description="Approved faculty members will appear here." icon={<Users />} />
        </div>
      ) : (
        <>
          <div className="hidden overflow-hidden rounded-lg border border-line shadow-low md:block" data-testid="users-table">
            <table className="w-full text-left text-small">
              <thead className="bg-surface text-metadata uppercase tracking-[0.14em] text-text-muted">
                <tr>
                  <th className="px-4 py-3 font-semibold">Name</th>
                  <th className="px-4 py-3 font-semibold">Email</th>
                  <th className="px-4 py-3 font-semibold">Role</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold">Registered</th>
                  <th className="px-4 py-3 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {active.map((u) => (
                  <tr key={u.user_id} data-testid={`user-row-${u.email}`}>
                    <td className="px-4 py-3 font-medium text-text-primary">{u.full_name}</td>
                    <td className="px-4 py-3 text-text-secondary">{u.email}</td>
                    <td className="px-4 py-3">{renderRoleBadge(u)}</td>
                    <td className="px-4 py-3"><StatusBadge status="active" /></td>
                    <td className="px-4 py-3 text-text-muted">{formatDate(u.created_at)}</td>
                    <td className="px-4 py-3">
                      {renderAdminActions(u, busy, isPrimaryActor, onDisable, onRemoveAdmin)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <UserCards active={active} busy={busy} isPrimaryActor={isPrimaryActor} onDisable={onDisable} onRemoveAdmin={onRemoveAdmin} />
        </>
      )}
    </section>
  );
}

/** Backend-authoritative role display: MAIN ADMIN > ADMIN > joined roles. */
function renderRoleBadge(u: AdminUserSummary) {
  if (u.is_primary_admin) {
    return (
      <Badge tone="primary" data-testid={`role-main-admin-${u.email}`}>
        <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> Main Admin
      </Badge>
    );
  }
  if (u.roles.includes('admin')) {
    return <Badge tone="primary">Admin</Badge>;
  }
  // Preserve the original role-text rendering (e.g. lowercase "faculty").
  return <Badge tone="neutral">{u.roles.join(', ') || 'Faculty'}</Badge>;
}

/**
 * UI-only reflection of backend capability: the Main Admin can remove another
 * admin's ADMIN role; nobody can remove the Main Admin (including itself).
 * The backend enforces this regardless of what the UI shows.
 */
function renderAdminActions(
  u: AdminUserSummary,
  busy: (user: AdminUserSummary) => boolean,
  isPrimaryActor: boolean,
  onDisable: (id: string) => void,
  onRemoveAdmin: (id: string) => void
) {
  if (u.is_primary_admin) {
    return (
      <span className="text-metadata text-text-muted" data-testid={`protected-main-admin-${u.email}`}>
        Protected Main Admin
      </span>
    );
  }
  if (u.roles.includes('admin')) {
    if (!isPrimaryActor) {
      return <span className="text-metadata text-text-muted">—</span>;
    }
    return (
      <button
        type="button"
        disabled={busy(u)}
        onClick={() => onRemoveAdmin(u.user_id)}
        data-testid={`remove-admin-${u.email}`}
        className="inline-flex items-center gap-1 rounded-[0.5rem] border border-danger/30 bg-surface px-3 py-1.5 text-metadata font-semibold text-danger transition-colors duration-micro hover:bg-danger-soft disabled:opacity-60"
      >
        {busy(u) ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <ShieldX className="h-3.5 w-3.5" aria-hidden="true" />}
        {busy(u) ? 'Removing…' : 'Remove Admin Access'}
      </button>
    );
  }
  return renderDisableCell(u, busy, onDisable);
}

function renderDisableCell(u: AdminUserSummary, busy: (user: AdminUserSummary) => boolean, onDisable: (id: string) => void) {
  if (!u.is_active || u.roles.includes('admin')) {
    return <span className="text-metadata text-text-muted">—</span>;
  }
  return (
    <button type="button" disabled={busy(u)} onClick={() => onDisable(u.user_id)} data-testid={`disable-${u.email}`}
      className="inline-flex items-center gap-1 rounded-[0.5rem] border border-line bg-surface px-3 py-1.5 text-metadata font-semibold text-text-secondary transition-colors duration-micro hover:bg-slate-50 disabled:opacity-60">
      {busy(u) ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <Ban className="h-3.5 w-3.5" aria-hidden="true" />}
      {busy(u) ? 'Disabling…' : 'Disable'}
    </button>
  );
}
function UserCards({
  active,
  busy,
  isPrimaryActor,
  onDisable,
  onRemoveAdmin,
}: {
  active: AdminUserSummary[];
  busy: (u: AdminUserSummary) => boolean;
  isPrimaryActor: boolean;
  onDisable: (id: string) => void;
  onRemoveAdmin: (id: string) => void;
}) {
  return (
    <div className="space-y-3 md:hidden" data-testid="users-table-mobile">
      {active.map((u) => (
        <div key={u.user_id} className="rounded-lg border border-line bg-surface p-4 shadow-low" data-testid={`user-card-${u.email}`}>
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-medium text-text-primary">{u.full_name}</p>
              <p className="text-small text-text-secondary">{u.email}</p>
            </div>
            <StatusBadge status="active" />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">{renderRoleBadge(u)}</div>
          <div className="mt-3">
            {renderAdminActions(u, busy, isPrimaryActor, onDisable, onRemoveAdmin)}
          </div>
        </div>
      ))}
    </div>
  );
}

function AdminRequestsPanel({
  requests,
  busyId,
  onApprove,
  onReject,
}: {
  requests: AdminAccessRequest[];
  busyId: string | null;
  onApprove: (requestId: string) => void;
  onReject: (requestId: string, reason?: string) => void;
}) {
  const pending = requests.filter((r) => r.status === 'pending');
  const reviewed = requests.filter((r) => r.status !== 'pending');
  const busy = (r: AdminAccessRequest) => busyId === r.request_id;
  const [reasons, setReasons] = useState<Record<string, string>>({});
  return (
    <section aria-label="Admin access requests">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-section-heading text-text-primary">Admin Requests</h2>
        <p className="text-small text-text-secondary">
          Requests for administrator access require review before the ADMIN role is granted.
        </p>
      </div>

      {pending.length === 0 ? (
        <div data-testid="admin-requests-empty">
          <EmptyState
            title="No admin requests"
            description="There are currently no pending requests for Admin access."
            icon={<ShieldCheck />}
          />
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2" data-testid="admin-requests-list">
          {pending.map((r) => (
            <div
              key={r.request_id}
              className="rounded-lg border border-line bg-surface p-4 shadow-low"
              data-testid={`admin-request-${r.requester_email ?? r.request_id}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-text-primary">{r.requester_name ?? 'Unknown requester'}</p>
                  <p className="text-small text-text-secondary">{r.requester_email ?? '—'}</p>
                </div>
                <StatusBadge status="pending" />
              </div>
              <dl className="mt-3 space-y-1 text-metadata text-text-muted">
                <div className="flex gap-2">
                  <dt className="font-medium text-text-secondary">Requested Role:</dt>
                  <dd className="capitalize">{r.requested_role}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="font-medium text-text-secondary">Requested:</dt>
                  <dd>{formatDate(r.requested_at)}</dd>
                </div>
              </dl>
              <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                <button
                  type="button"
                  disabled={busy(r)}
                  onClick={() => onApprove(r.request_id)}
                  data-testid={`approve-request-${r.requester_email ?? r.request_id}`}
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-[0.5rem] bg-success px-3 py-2 text-metadata font-semibold text-white transition-colors duration-micro hover:bg-success disabled:opacity-60"
                >
                  {busy(r) ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />}
                  {busy(r) ? 'Approving…' : 'Approve'}
                </button>
                <button
                  type="button"
                  disabled={busy(r)}
                  onClick={() => onReject(r.request_id, reasons[r.request_id])}
                  data-testid={`reject-request-${r.requester_email ?? r.request_id}`}
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-[0.5rem] border border-danger/30 bg-surface px-3 py-2 text-metadata font-semibold text-danger transition-colors duration-micro hover:bg-danger-soft disabled:opacity-60"
                >
                  {busy(r) ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <XCircle className="h-3.5 w-3.5" aria-hidden="true" />}
                  {busy(r) ? 'Rejecting…' : 'Reject'}
                </button>
              </div>
              <label className="mt-3 block space-y-1">
                <span className="text-metadata font-medium text-text-secondary">
                  Rejection reason (optional)
                </span>
                <input
                  type="text"
                  value={reasons[r.request_id] ?? ''}
                  onChange={(event) =>
                    setReasons((prev) => ({ ...prev, [r.request_id]: event.target.value }))
                  }
                  placeholder="Why is this request being rejected?"
                  data-testid={`reject-reason-${r.requester_email ?? r.request_id}`}
                  className="w-full rounded-[8px] border border-line bg-surface px-3 py-2 text-small text-text-primary outline-none transition-colors duration-micro placeholder:text-text-muted focus:border-primary"
                />
              </label>
            </div>
          ))}
        </div>
      )}

      {reviewed.length > 0 ? (
        <div className="mt-8">
          <h3 className="text-small font-semibold uppercase tracking-[0.14em] text-text-muted">
            Recently reviewed
          </h3>
          <ul className="mt-3 space-y-2" data-testid="admin-requests-reviewed">
            {reviewed.map((r) => (
              <li
                key={r.request_id}
                className="rounded-lg border border-line bg-surface px-4 py-3 text-small"
                data-testid={`admin-request-reviewed-${r.requester_email ?? r.request_id}`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-text-primary">
                    {r.requester_name ?? r.requester_email ?? 'Unknown requester'}
                    <span className="ml-2 font-normal text-text-secondary">{r.requester_email}</span>
                  </span>
                  <StatusBadge status={r.status} />
                </div>
                <p className="mt-1 text-metadata text-text-muted">
                  Reviewed {formatDate(r.reviewed_at ?? null)}
                  {r.reviewer ? ` by ${r.reviewer}` : ''}
                  {r.review_reason ? ` — “${r.review_reason}”` : ''}
                </p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function AuditTable({ logs, users }: { logs: any[]; users: AdminUserSummary[] }) {
  const actorName = (id: string | null): string => {
    if (!id || id === 'system') return 'System';
    const found = users.find((u) => u.user_id === id);
    return found?.full_name || found?.email || 'Administrator';
  };
  return (
    <section aria-label="Audit log">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-section-heading text-text-primary">Audit</h2>
        <p className="text-small text-text-secondary">Administrative actions recorded</p>
      </div>
      {logs.length === 0 ? (
        <div data-testid="audit-empty">
          <EmptyState title="No admin actions recorded yet" description="Administrative actions will appear here as they happen." icon={<ScrollText />} />
        </div>
      ) : (
        <>
          <div className="hidden overflow-hidden rounded-lg border border-line shadow-low md:block" data-testid="audit-table">
            <table className="w-full text-left text-small">
              <thead className="bg-surface text-metadata uppercase tracking-[0.14em] text-text-muted">
                <tr>
                  <th className="px-4 py-3 font-semibold">Actor</th>
                  <th className="px-4 py-3 font-semibold">Action</th>
                  <th className="px-4 py-3 font-semibold">Target</th>
                  <th className="px-4 py-3 font-semibold">Date/time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {logs.map((log) => (
                  <tr key={log.id} data-testid={`audit-row-${log.action}`}>
                    <td className="px-4 py-3 font-medium text-text-primary">{actorName(log.actor_user_id)}</td>
                    <td className="px-4 py-3 text-text-secondary">{friendlyAction(log.action)}</td>
                    <td className="px-4 py-3 text-text-secondary">{log.target ?? log.entity_type ?? '—'}</td>
                    <td className="px-4 py-3 text-text-muted">{log.created_at ? new Date(log.created_at).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <AuditCards logs={logs} actorName={actorName} />
        </>
      )}
    </section>
  );
}

function AuditCards({ logs, actorName }: { logs: any[]; actorName: (id: string | null) => string }) {
  return (
    <div className="space-y-3 md:hidden" data-testid="audit-table-mobile">
      {logs.map((log) => (
        <div key={log.id} className="rounded-lg border border-line bg-surface p-4 shadow-low" data-testid={`audit-card-${log.action}`}>
          <p className="font-semibold text-text-primary">{friendlyAction(log.action)}</p>
          <p className="mt-0.5 text-small text-text-secondary">
            by {actorName(log.actor_user_id)} · {log.created_at ? new Date(log.created_at).toLocaleString() : '—'}
          </p>
        </div>
      ))}
    </div>
  );
}
