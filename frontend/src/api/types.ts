// frontend/src/api/types.ts

export interface TenantInfo {
  tenant_id: string;
  name: string;
  email: string;
  roles: string[];
}

export type IdentityType =
  | "User"
  | "ServicePrincipal"
  | "ManagedIdentity"
  | "Group";

export interface ObservedAction {
  action: string;
  resource: string | null;
  count: number;
  first_seen: string;
  last_seen: string;
}

export interface CurrentRole {
  role_id: string;
  role_name: string;
  scope: string;
  assignment_type: string;
  is_permanent: boolean;
}

export interface IdentityProfile {
  id: string;
  tenant_id: string;
  identity_type: IdentityType;
  object_id: string;
  display_name: string;
  upn: string | null;
  app_id: string | null;
  current_roles: CurrentRole[];
  observed_actions: ObservedAction[];
  risk_score: number;
  action_count: number;
  last_seen: string | null;
  first_seen: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface ActionEvent {
  id: string;
  tenant_id: string;
  identity_id: string;
  identity_display_name: string;
  action: string;
  resource: string | null;
  resource_type: string | null;
  result: string;
  source: string;
  correlation_id: string | null;
  ip_address: string | null;
  timestamp: string;
}

export interface SyncStatus {
  audit_log: { last_sync: string | null; has_delta: boolean } | null;
  sign_in_log: { last_sync: string | null } | null;
}

// --- Phase 3: Role Recommendations ---

export interface PermissionGap {
  permission: string;
  risk_weight: "low" | "medium" | "high" | "critical";
  is_used: boolean;
}

export interface BuiltInRoleMatch {
  role_id: string;
  role_name: string;
  scope: "entra" | "azure";
  match_score: number;
  permissions_matched: number;
  permissions_total: number;
  excess_permissions: string[];
}

export interface CustomRoleDefinition {
  name: string;
  description: string;
  scope: string;
  permissions:
    | string[]
    | {
        actions: string[];
        notActions: string[];
        dataActions: string[];
        notDataActions: string[];
      };
  is_assignable_scopes: string[];
}

export interface RoleRecommendation {
  id: string;
  tenant_id: string;
  identity_id: string;
  identity_display_name: string;
  identity_type: string;
  current_roles: CurrentRole[];
  required_permissions: string[];
  permission_gaps: PermissionGap[];
  best_builtin_match: BuiltInRoleMatch | null;
  alternative_builtins: BuiltInRoleMatch[];
  custom_role: CustomRoleDefinition;
  reduction_score: number;
  computed_at: string;
}

export type ExportFormat = "terraform" | "bicep" | "arm";

export interface ExportResult {
  format: ExportFormat;
  identity_id: string;
  content: string;
  filename: string;
}
