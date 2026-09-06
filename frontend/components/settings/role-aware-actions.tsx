import { Plus, Users, User } from 'lucide-react';
import { useAuth } from '@/contexts/auth-context';
import { ButtonLink } from '@/components/ui/button';

export function RoleAwareActions() {
  const { user } = useAuth();

  if (!user) return null;

  const isAdmin = user.roles.includes('admin');
  const isFaculty = user.roles.includes('faculty') && !isAdmin;

  return (
    <nav aria-label="Settings shortcuts" className="flex flex-wrap gap-3">
      <ButtonLink href="/create" variant="outline" leadingIcon={<Plus className="h-4 w-4" />}>
        Create a new paper
      </ButtonLink>

      {isFaculty ? (
        <ButtonLink href="/dashboard" variant="outline" leadingIcon={<Users className="h-4 w-4" />}>
          View your papers
        </ButtonLink>
      ) : null}

      {isAdmin ? (
        <ButtonLink href="/admin" variant="outline" leadingIcon={<User className="h-4 w-4" />}>
          Manage people &amp; access
        </ButtonLink>
      ) : null}
    </nav>
  );
}

