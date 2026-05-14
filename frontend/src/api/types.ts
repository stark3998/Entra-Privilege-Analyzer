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

// --- Phase 4: Drift Detection ---

export type DriftSeverity = "low" | "medium" | "high" | "critical";
export type DriftStatus = "open" | "acknowledged" | "escalated" | "resolved";
export type DriftType = "first_seen" | "frequency_anomaly";

export interface DriftAlert {
  id: string;
  tenant_id: string;
  identity_id: string;
  identity_display_name: string;
  drift_type: DriftType;
  action: string;
  resource: string | null;
  severity: DriftSeverity;
  status: DriftStatus;
  z_score: number | null;
  baseline_mean: number | null;
  baseline_stddev: number | null;
  observed_count: number | null;
  details: string;
  detected_at: string;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

export interface BaselineStats {
  identity_id: string;
  action: string;
  resource: string | null;
  mean: number;
  stddev: number;
  sample_count: number;
  window_start: string;
  window_end: string;
}

// --- Phase 5: Best Practices ---

export type ViolationType =
  | "stale_identity"
  | "permanent_admin"
  | "no_pim"
  | "sp_credential_expiry"
  | "separation_of_duties"
  | "overprivileged"
  | "mfa_gap"
  | "role_assignable_group";

export type ViolationPriority = "critical" | "high" | "medium" | "low" | "info";

export interface BestPracticeViolation {
  id: string;
  tenant_id: string;
  identity_id: string;
  identity_display_name: string;
  identity_type: string;
  violation_type: ViolationType;
  priority: ViolationPriority;
  title: string;
  description: string;
  remediation_steps: string[];
  affected_roles: string[];
  detected_at: string;
  resolved: boolean;
}

export interface BestPracticeSummary {
  tenant_id: string;
  total_violations: number;
  by_priority: Record<string, number>;
  by_type: Record<string, number>;
  compliance_score: number;
  evaluated_at: string;
}

// --- Phase 6: Executive Dashboard ---

export interface DashboardSummary {
  tenant_id: string;
  total_identities: number;
  total_actions: number;
  identities_by_type: Record<string, number>;
  avg_risk_score: number;
  high_risk_count: number;
  drift_alerts_open: number;
  drift_alerts_by_severity: Record<string, number>;
  compliance_score: number;
  top_risky_identities: Array<{
    id: string;
    display_name: string;
    identity_type: string;
    risk_score: number;
  }>;
  recommendations_count: number;
  avg_reduction_score: number;
  computed_at: string;
}

export interface TrendPoint {
  date: string;
  value: number;
}

export interface DashboardTrends {
  risk_score_trend: TrendPoint[];
  drift_alerts_trend: TrendPoint[];
  actions_trend: TrendPoint[];
}

export interface Narrative {
  id: string;
  content: string;
  generated_at: string;
  expires_at: string;
}

// --- Phase 7: Settings & Reports ---

export interface TenantSettings {
  id: string;
  tenant_id: string;
  sync_schedule_hours: number;
  baseline_window_days: number;
}

export interface ReportFormat {
  format: "pdf" | "pptx";
}

// --- Projects ---

export type ProjectStatus = "active" | "setup" | "error";
export type MemberRole = "admin" | "operator" | "viewer" | "owner";
export type ScanStatus = "queued" | "running" | "completed" | "failed";

export interface PermissionValidationResult {
  valid: boolean;
  granted: string[];
  missing: string[];
  error?: string;
}

export interface Project {
  id: string;
  owner_id: string;
  owner_email: string;
  name: string;
  target_tenant_id: string;
  target_tenant_name: string;
  client_id: string;
  status: ProjectStatus;
  permission_status: PermissionValidationResult | null;
  last_scan_at: string | null;
  last_scan_status: string | null;
  identity_count: number;
  risk_score: number;
  sync_schedule_hours: number;
  baseline_window_days: number;
  created_at: string;
  updated_at: string;
}

export interface CreateProjectPayload {
  name: string;
  target_tenant_id: string;
  target_tenant_name: string;
  client_id: string;
  client_secret: string;
}

export interface UpdateProjectPayload {
  name?: string;
  sync_schedule_hours?: number;
  baseline_window_days?: number;
}

export interface ProjectMember {
  id: string;
  user_id: string;
  email: string;
  role: MemberRole;
  status: "pending" | "accepted";
}

export interface ProjectMembersResponse {
  members: ProjectMember[];
  current_user_role: MemberRole;
}

export interface InviteMemberPayload {
  email: string;
  role: string;
}

export interface ScanPhase {
  name: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  items_processed: number;
}

export interface ScanRecord {
  id: string;
  project_id: string;
  target_tenant_id: string;
  scan_type: "full" | "incremental";
  status: ScanStatus;
  phases: ScanPhase[];
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

// --- Analytics ---

export interface AnalyticsData {
  tenant_id: string;
  days: number;
  total_actions: number;
  unique_active_identities: number;
  avg_actions_per_identity: number;
  failed_action_pct: number;
  new_identities_count: number;
  daily_action_counts: TrendPoint[];
  top_actions: { action: string; count: number }[];
  most_active_identities: {
    identity_id: string;
    display_name: string;
    identity_type: string;
    count: number;
  }[];
  actions_by_source: Record<string, number>;
  success_vs_failure: Record<string, number>;
  top_resources: {
    resource: string;
    resource_type: string;
    count: number;
  }[];
  top_roles: { role_name: string; count: number }[];
  permission_utilization: { used: number; unused: number };
  permanent_vs_pim: { permanent: number; pim: number };
  overprivileged_count: number;
  violations_by_type: Record<string, number>;
  stale_identity_counts: Record<string, number>;
  credential_expiry_violations: {
    identity_id: string;
    identity_display_name: string;
    detected_at: string;
  }[];
  recent_drift_alerts: DriftAlert[];
  computed_at: string;
}

// --- App Registrations ---

export interface CredentialInfo {
  key_id: string;
  credential_type: 'password' | 'certificate';
  display_name: string | null;
  start_date: string | null;
  end_date: string | null;
  days_until_expiry: number | null;
  age_days: number | null;
  is_expired: boolean;
}

export interface AppRegistrationProfile {
  id: string;
  tenant_id: string;
  app_id: string;
  display_name: string;
  sign_in_audience: string;
  is_multi_tenant: boolean;
  password_credentials: CredentialInfo[];
  key_credentials: CredentialInfo[];
  owner_count: number;
  high_risk_permissions: string[];
  fetched_at: string;
}

// --- Conditional Access ---

export interface ConditionalAccessPolicy {
  id: string;
  tenant_id: string;
  display_name: string;
  state: string;
  created_date_time: string | null;
  modified_date_time: string | null;
  conditions: Record<string, unknown>;
  grant_controls: Record<string, unknown>;
}

// --- Groups ---

export interface GroupProfile {
  id: string;
  tenant_id: string;
  display_name: string;
  is_role_assignable: boolean;
  is_dynamic: boolean;
  membership_rule: string | null;
  member_count: number;
  transitive_member_count: number;
  owner_count: number;
  roles_assigned: string[];
  created_at: string | null;
}

// --- Custom Roles ---

export interface CustomRoleProfile {
  id: string;
  tenant_id: string;
  display_name: string;
  description: string;
  is_enabled: boolean;
  permissions: string[];
  assignment_count: number;
  has_wildcard: boolean;
  has_escalation_paths: boolean;
  created_at: string | null;
}

// --- Access Reviews ---

export interface AccessReviewDefinition {
  id: string;
  tenant_id: string;
  display_name: string;
  status: string;
  scope_type: string | null;
  created_at: string | null;
}

// --- SoD Rules ---

export interface SodConflictRule {
  id: string;
  tenant_id: string;
  role_a_name: string;
  role_b_name: string;
  severity: string;
  rationale: string;
  is_custom: boolean;
  enabled: boolean;
}

// --- Remediation ---

export interface RemediationAction {
  id: string;
  tenant_id: string;
  project_id: string;
  action_type: string;
  target_identity_id: string;
  target_resource_id: string | null;
  requested_by: string;
  approved_by: string | null;
  status: string;
  justification: string;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
}

// --- Scan Schedule ---

export interface ScanSchedule {
  id: string;
  project_id: string;
  cron_expression: string | null;
  job_types: string[];
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
}

// --- Alert Rule ---

export interface AlertRule {
  id: string;
  project_id: string;
  tenant_id: string;
  rule_type: string;
  condition: Record<string, unknown>;
  channel: { channel_type: string; config: Record<string, unknown> };
  severity_filter: string | null;
  enabled: boolean;
}
