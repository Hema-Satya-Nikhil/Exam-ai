"use client";

import { Suspense } from 'react';
import { LogOut } from 'lucide-react';

import { AppShell } from '@/components/layout/app-shell';
import { EmptyState } from '@/components/ui/empty-state';
import { SettingsSkeleton } from '@/components/settings/settings-skeleton';
import { AccountSummary } from '@/components/settings/account-summary';
import { SecuritySection } from '@/components/settings/security-section';
import { RoleAwareActions } from '@/components/settings/role-aware-actions';
import { useAuth } from '@/contexts/auth-context';
import type { CurrentUser } from '@/lib/api';

export default function SettingsPage() {
  return (
    <AppShell>
      <Suspense fallback={<SettingsSkeleton />}>
        <SettingsContent />
      </Suspense>
    </AppShell>
  );
}

function SettingsContent() {
  const { user, loading: authLoading } = useAuth();

  if (authLoading) {
    return (
      <main className="min-h-screen bg-background">
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-10">
          <SettingsSkeleton />
        </div>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="min-h-screen bg-background">
        <div className="mx-auto max-w-2xl px-4 py-12 sm:px-6 lg:px-10">
          <EmptyState
            icon={<LogOut className="h-10 w-10" />}
            title="Sign in to manage your settings"
            description="Your account settings are only available to authenticated users."
            actionLabel="Go to sign in"
            actionVariant="primary"
            onAction={() => {
              window.location.href = '/login';
            }}
          />
        </div>
      </main>
    );
  }

  return <SettingsView user={user} />;
}

interface SettingsViewProps {
  user: CurrentUser;
}

function SettingsView({ user }: SettingsViewProps) {
  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-10">
        {/* Page header */}
        <header className="mb-8">
          <p className="text-metadata font-semibold uppercase tracking-[0.18em] text-text-muted">
            Settings
          </p>
          <h1 className="mt-2 text-heading tracking-tight text-text-primary">
            Manage your account and application preferences.
          </h1>
          <p className="mt-3 max-w-2xl text-small text-text-secondary">
            Your account is used to attribute every generated paper, approval, and export.
            Environment configuration is managed by your administrator and kept out of the browser.
          </p>
        </header>

        {/* Your Account + Role-aware shortcuts */}
        <section className="mb-8 grid gap-8 lg:grid-cols-2 lg:items-start">
          <AccountSummary user={user} />
          <div className="lg:mt-0">
            <div className="rounded-lg border border-line bg-surface p-5 shadow-low">
              <h2 className="text-section-heading text-text-primary mb-3">
                Quick actions
              </h2>
              <RoleAwareActions />
            </div>
          </div>
        </section>

        {/* Security */}
        <section className="mb-8">
          <SecuritySection user={user} />
        </section>
      </div>
    </main>
  );
}
