// frontend/src/components/layout/RoleGate.tsx
import type { ReactNode } from "react";
import { useAuth } from "@/auth/useAuth";

interface RoleGateProps {
  /** Roles that grant access. User must have at least one. */
  roles: string[];
  children: ReactNode;
  fallback?: ReactNode;
}

/**
 * Conditionally renders children if the user has at least one of the required roles.
 * In local mode, all roles are granted so children always render.
 */
export function RoleGate({ roles, children, fallback = null }: RoleGateProps) {
  const { roles: userRoles } = useAuth();
  const hasAccess = roles.some((r) => userRoles.includes(r));

  if (!hasAccess) return <>{fallback}</>;
  return <>{children}</>;
}
