"use client";

import { useRouter } from 'next/navigation';
import { LogOut, Shield } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/auth-context';
import { CurrentUser } from '@/lib/api';

export interface SecuritySectionProps {
  user: CurrentUser;
}

/**
 * Security section — displays only what the backend actually supports.
 * No password-change, session-management, or 2FA APIs exist, so those
 * features are intentionally not invented in this phase.
 */
export function SecuritySection({ user }: SecuritySectionProps) {
  const { logout } = useAuth();
  const router = useRouter();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-section-heading">Security</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-[160px_1fr] gap-x-6 gap-y-3">
          <dt className="text-metadata text-text-muted">Session</dt>
          <dd className="text-body text-text-primary">
            Managed via authentication tokens
          </dd>

          <dt className="text-metadata text-text-muted">Password</dt>
          <dd className="text-body text-text-primary">
            Set during registration — contact your administrator to update
          </dd>

          <dt className="text-metadata text-text-muted">Two-factor authentication</dt>
          <dd className="text-body text-text-secondary">Not available</dd>
        </dl>

        <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-line pt-4">
          <Button
            variant="outline"
            leadingIcon={<LogOut className="h-4 w-4" />}
            onClick={() => {
              void logout();
              router.push('/login');
            }}
          >
            Sign out
          </Button>

          <span className="inline-flex items-center gap-1.5 text-xs text-text-muted">
            <Shield className="h-3.5 w-3.5" />
            Authenticated as {user.email}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
