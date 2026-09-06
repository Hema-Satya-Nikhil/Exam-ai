import {
  ClipboardList,
  FilePlus2,
  LayoutDashboard,
  ListChecks,
  ScrollText,
  Settings,
  Users,
  Workflow
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** Path prefix used for active-state matching. */
  match: string;
  /** Only rendered when the signed-in user has this role. */
  requiresRole?: 'admin';
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

/**
 * Single source of truth for app navigation.
 * RBAC is unchanged: admin items simply don't render unless the existing
 * auth context reports the admin role.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    title: 'Workspace',
    items: [
      { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, match: '/dashboard' },
      { label: 'Create Paper', href: '/create', icon: FilePlus2, match: '/create' },
      { label: 'Recent Papers', href: '/dashboard#recent', icon: ClipboardList, match: '/dashboard#recent' },
      { label: 'Review', href: '/review', icon: ListChecks, match: '/review' },
      { label: 'Productivity', href: '/productivity', icon: Workflow, match: '/productivity' }
    ]
  },
  {
    title: 'Admin',
    items: [
      { label: 'People & Access', href: '/admin', icon: Users, match: '/admin', requiresRole: 'admin' },
      { label: 'Audit', href: '/admin?tab=audit', icon: ScrollText, match: '/admin?tab=audit', requiresRole: 'admin' }
    ]
  },
  {
    title: 'System',
    items: [{ label: 'Settings', href: '/settings', icon: Settings, match: '/settings' }]
  }
];

/** Context label shown in the topbar for the current route. */
export function getPageContext(pathname: string): string {
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      const base = item.match.split('?')[0].split('#')[0];
      if (base !== '/' && pathname.startsWith(base)) return item.label;
    }
  }
  return 'Workspace';
}
