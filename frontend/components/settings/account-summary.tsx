import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { StatusBadge } from '@/components/ui/badge';
import { CurrentUser } from '@/lib/api';

export interface AccountSummaryProps {
  user: CurrentUser;
}

/** Compact account overview — uses only real backend fields. */
export function AccountSummary({ user }: AccountSummaryProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-section-heading">Your Account</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-[140px_1fr] gap-x-6 gap-y-3">
          <dt className="text-metadata text-text-muted">Name</dt>
          <dd className="text-body text-text-primary">{user.full_name}</dd>

          <dt className="text-metadata text-text-muted">Email</dt>
          <dd className="text-body text-text-primary break-all">{user.email}</dd>

          <dt className="text-metadata text-text-muted">Role</dt>
          <dd>
            {user.roles.length > 0 ? (
              <Badge tone="primary">
                {user.roles.map((r) => r.charAt(0).toUpperCase() + r.slice(1)).join(', ')}
              </Badge>
            ) : (
              <span className="text-text-muted">—</span>
            )}
          </dd>

          <dt className="text-metadata text-text-muted">Account status</dt>
          <dd>
            <StatusBadge status={user.is_active ? 'active' : 'disabled'} />
          </dd>
        </dl>
      </CardContent>
    </Card>
  );
}
