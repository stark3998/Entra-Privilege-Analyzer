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
  checkpoint_next_link: string | null;
}

export interface ScanRecord {
  id: string;
  project_id: string;
  target_tenant_id: string;
  scan_type: "full" | "incremental";
  auth_mode: "app" | "delegated";
  status: ScanStatus;
  phases: ScanPhase[];
  started_at: string;
  completed_at: string | null;
  resumed_from_scan_id: string | null;
  error_message: string | null;
}

export interface ScanStreamEvent {
  id: string;
  type: string;
  message: string;
  project_id: string;
  scan_id: string | null;
  level: "info" | "warning" | "error";
  phase: string | null;
  status: string | null;
  items_processed: number | null;
  timestamp: string;
  details: Record<string, unknown>;
}

export interface PollScanEventsResponse {
  events: ScanStreamEvent[];
  cursor: string | null;
  scan_status: ScanStatus | null;
  has_more: boolean;
}

export interface DelegatedPermissionsCheck {
  sufficient: boolean;
  granted_scopes: string[];
  missing_scopes: string[];
  error?: string;
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

// --- PIM Sessions ---

export type PimSessionStatus = "active" | "expired" | "deactivated";
export type PimSessionScope = "entra_directory" | "azure_rbac";
export type PimSessionAnomalyType =
  | "unusual_activation_time"
  | "new_location"
  | "first_time_role"
  | "high_volume_actions"
  | "sensitive_action"
  | "no_justification";

export interface TicketInfo {
  ticket_number: string | null;
  ticket_system: string | null;
}

export interface ApprovalInfo {
  approval_id: string | null;
  approver_id: string | null;
  approver_display_name: string | null;
  approval_status: string | null;
  approved_at: string | null;
}

export interface SessionLocationInfo {
  ip_address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface PimSessionAnomaly {
  anomaly_type: PimSessionAnomalyType;
  severity: string;
  details: string;
  detected_at: string;
}

export interface PimSession {
  id: string;
  tenant_id: string;
  principal_id: string;
  principal_display_name: string;
  principal_upn: string | null;
  identity_id: string;
  role_definition_id: string;
  role_name: string;
  scope: string;
  session_scope: PimSessionScope;
  activation_time: string;
  expiry_time: string;
  actual_deactivation_time: string | null;
  duration_minutes: number;
  status: PimSessionStatus;
  is_active: boolean;
  justification: string | null;
  ticket_info: TicketInfo | null;
  approval_info: ApprovalInfo | null;
  activation_request_id: string | null;
  audit_event_count: number;
  sign_in_event_count: number;
  total_event_count: number;
  unique_actions: string[];
  locations: SessionLocationInfo[];
  anomalies: PimSessionAnomaly[];
  risk_score: number;
  created_at: string;
  updated_at: string;
  last_event_sync_at: string | null;
}

export interface PimSessionAnalytics {
  tenant_id: string;
  total_sessions: number;
  active_sessions: number;
  expired_sessions: number;
  sessions_with_anomalies: number;
  avg_session_duration_minutes: number;
  top_activated_roles: { role_name: string; count: number }[];
  top_activators: { principal_display_name: string; count: number }[];
  activations_by_hour: Record<number, number>;
  activations_by_day: { date: string; count: number }[];
  anomaly_counts_by_type: Record<string, number>;
  computed_at: string;
}

// --- Access Path Analysis ---

export type AccessPathNodeType =
  | "user"
  | "service_principal"
  | "application"
  | "group"
  | "directory_role"
  | "app_permission";

export type AccessPathEdgeType =
  | "owns_app"
  | "app_has_sp"
  | "sp_has_app_role"
  | "sp_has_directory_role"
  | "owns_group"
  | "member_of_group"
  | "group_has_role"
  | "owns_sp"
  | "has_directory_role"
  | "can_modify_any_app";

export type AccessPathRisk = "critical" | "high" | "medium";

export interface AccessPathNode {
  id: string;
  node_type: AccessPathNodeType;
  display_name: string;
  properties: Record<string, unknown>;
}

export interface AccessPathEdge {
  edge_type: AccessPathEdgeType;
  description: string;
}

export interface AccessPathStep {
  node: AccessPathNode;
  edge: AccessPathEdge | null;
}

export interface AccessPath {
  id: string;
  path_type: string;
  risk_level: AccessPathRisk;
  steps: AccessPathStep[];
  target_privilege: string;
  description: string;
  exploitability: string;
}

export interface AccessPathAnalysis {
  id: string;
  tenant_id: string;
  identity_id: string;
  identity_display_name: string;
  identity_type: string;
  paths: AccessPath[];
  total_paths: number;
  critical_paths: number;
  high_paths: number;
  medium_paths: number;
  highest_risk: string;
  analyzed_at: string;
}

export interface AccessPathSummary {
  total_identities_with_paths: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  top_path_types: { path_type: string; count: number }[];
}

// --- Governance UX ---

export type GovernanceWorkflowType =
  | "least_privilege_migration"
  | "continuous_drift"
  | "jit_access"
  | "incident_containment"
  | "access_review"
  | "restore";

export type GovernanceWorkflowStatus =
  | "draft"
  | "analyzing"
  | "waiting_approval"
  | "approved"
  | "executing"
  | "canary"
  | "grace_period"
  | "verifying"
  | "completed"
  | "failed"
  | "compensating"
  | "restored"
  | "cancelled";

export type GovernanceWorkflowDecision =
  | "approve"
  | "transition";

export type AuthorizationMode =
  | "split_applications"
  | "combined_application"
  | "delegated_obo";

export interface WorkflowStep {
  id: string;
  name: string;
  status: string;
  action_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  details: Record<string, unknown>;
}

export interface GovernanceWorkflow {
  id: string;
  tenant_id: string;
  project_id: string;
  identity_id: string;
  kind: GovernanceWorkflowType;
  status: GovernanceWorkflowStatus;
  correlation_id: string;
  idempotency_key: string;
  requested_by: string;
  persona_id: string | null;
  risk_assessment_id: string | null;
  snapshot_id: string | null;
  steps: WorkflowStep[];
  approvals: Record<string, unknown>[];
  completed_action_ids: string[];
  policy_decision: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  next_wake_at: string | null;
  error: string | null;
}

export interface WorkflowApprovalStep {
  step: number;
  label: string;
  owner: string | null;
  status: string;
  completed_at: string | null;
}

export interface WorkflowEvidenceRef {
  id: string;
  title: string;
  coverage_status: EvidenceCoverageStatus;
  source: string;
  collected_at: string | null;
}

export interface WorkflowActivity {
  id: string;
  actor: string;
  actor_role: string | null;
  action: string;
  message: string;
  created_at: string;
}

export type WorkflowInboxItem = GovernanceWorkflow;
export interface WorkflowInboxResponse extends PaginatedResponse<GovernanceWorkflow> {}
export type WorkflowDetail = GovernanceWorkflow;

export interface WorkflowDecisionRequest {
  target: GovernanceWorkflowStatus;
}

export type EvidenceCoverageStatus =
  | "covered"
  | "partial"
  | "missing"
  | "expired";

export interface EvidenceRecord {
  id: string;
  title: string;
  evidence_type: string;
  source: string;
  coverage_status: EvidenceCoverageStatus;
  control_family: string;
  linked_workflow_id: string | null;
  collected_at: string | null;
  expires_at: string | null;
  coverage_pct: number;
  owners: string[];
  summary: string;
}

export interface EvidenceCoverageFamily {
  family: string;
  covered: number;
  total: number;
  coverage_pct: number;
}

export interface DataQualityStatus {
  id: string;
  source: string;
  tenant_id: string;
  assessed_at: string;
  coverage_start: string | null;
  coverage_end: string | null;
  completeness: number;
  confidence: number;
  gaps: string[];
}

export interface EvidenceCoverageSummary {
  tenant_id: string;
  sources: DataQualityStatus[];
  complete: boolean;
}

export interface EvidenceAccessRecord {
  id: string;
  tenant_id: string;
  principal_id: string;
  entitlement_id: string;
  edge_type: string;
  scope_id: string | null;
  assignment_id: string | null;
  source: string;
  provenance: string[];
  condition: string | null;
  valid_from: string;
  valid_to: string | null;
  observed_at: string;
  confidence: number;
}

export interface IdentityEvidenceAccess {
  tenant_id: string;
  identity_id: string;
  items: EvidenceAccessRecord[];
}

export type PersonaRiskTolerance = "strict" | "balanced" | "expedited";
export type PersonaStatus =
  | "draft"
  | "evaluating"
  | "approved"
  | "published"
  | "superseded"
  | "retired";

export interface PersonaCatalogEntry {
  id: string;
  tenant_id: string;
  name: string;
  version: number;
  status: PersonaStatus;
  member_identity_ids: string[];
  common_permissions: string[];
  justified_rare_permissions: string[];
  builtin_role_id: string | null;
  builtin_role_name: string | null;
  custom_role_definition: Record<string, unknown> | null;
  match_score: number;
  escalation_findings: string[];
  sod_findings: string[];
  created_at: string;
  updated_at: string;
  approved_by: string | null;
}

export interface GovernancePolicyScope {
  id: string;
  name: string;
  scope_type: string;
  description: string;
  item_count: number;
  default_persona: string | null;
  constraints: string[];
  suggested_prompts: string[];
}

export interface GovernancePolicy {
  id: string;
  project_id: string;
  authorization_mode: AuthorizationMode;
  autonomous_max_impact: number;
  autonomous_min_confidence: number;
  autonomous_role_tiers: string[];
  high_impact_threshold: number;
  required_human_approvals: number;
  break_glass_identity_ids: string[];
  last_global_admin_protection: boolean;
  require_access_owner: boolean;
  created_at: string;
  updated_at: string;
  updated_by: string;
}

export interface AuthorizationReadiness {
  mode: AuthorizationMode;
  ready: boolean;
  collection_ready: boolean;
  mutation_ready: boolean;
  delegated_ready: boolean;
  missing: string[];
  warnings: string[];
  checked_at: string;
}

export type RoleChangeStatus =
  | "proposed"
  | "approved"
  | "canary_running"
  | "canary_failed"
  | "rolled_back"
  | "completed";

export type RoleChangeType = "add" | "remove" | "retain";

export type CanaryStageStatus =
  | "queued"
  | "running"
  | "passed"
  | "failed"
  | "rolled_back";

export interface RoleDiffSummary {
  id: string;
  identity_id: string;
  identity_display_name: string;
  identity_type: IdentityType;
  status: RoleChangeStatus;
  blast_radius: DriftSeverity;
  reduction_score: number;
  removed_permissions: number;
  added_permissions: number;
  current_role_count: number;
  proposed_role_count: number;
  canary_event_count: number;
  linked_workflow_id: string | null;
  proposed_by: string;
  proposed_at: string;
  canary_started_at: string | null;
}

export interface RoleDiffChange {
  role_name: string;
  scope: string;
  change_type: RoleChangeType;
  current_permissions: string[];
  proposed_permissions: string[];
  rationale: string | null;
}

export interface CanaryTimelineEvent {
  id: string;
  stage: string;
  status: CanaryStageStatus;
  timestamp: string;
  summary: string;
  metric_name: string | null;
  metric_value: number | null;
  threshold: string | null;
}

export interface RoleDiffDetail extends RoleDiffSummary {
  summary: string;
  change_set: RoleDiffChange[];
  canary_timeline: CanaryTimelineEvent[];
  rollback_window_minutes: number | null;
  rollback_reasons: string[];
  evidence_ids: string[];
}

export type RestoreConflictStatus =
  | "open"
  | "in_review"
  | "accepted_risk"
  | "resolved";

export interface RestoreConflict {
  id: string;
  title: string;
  conflict_type: string;
  severity: DriftSeverity;
  status: RestoreConflictStatus;
  source_connector: string;
  restore_point_label: string;
  identity_display_name: string | null;
  resource_scope: string;
  detected_at: string;
  summary: string;
  proposed_resolution: string | null;
  reviewer: string | null;
  evidence_count: number;
}

export interface RestoreConflictReviewRequest {
  status: Exclude<RestoreConflictStatus, "open">;
  resolution_note?: string;
}

export type GovernanceConnectorHealth =
  | "healthy"
  | "warning"
  | "degraded"
  | "offline";

export type GovernanceConnectorSyncMode = "scheduled" | "manual" | "paused";
export type GovernanceConnectorType =
  | "servicenow"
  | "teams"
  | "azure_devops";

export interface GovernanceConnector {
  id: string;
  project_id: string;
  connector_type: GovernanceConnectorType;
  endpoint: string;
  enabled: boolean;
  secret_reference: string | null;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ConnectorSyncJob {
  connector_id: string;
  job_id: string;
  status: string;
  queued_at: string;
}

export type ScopedCopilotRunStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed";

export interface ScopedCopilotScope {
  id: string;
  name: string;
  scope_type: string;
  description: string;
  item_count: number;
  default_persona: string | null;
  constraints: string[];
  suggested_prompts: string[];
}

export interface ScopedCopilotCitation {
  label: string;
  target_type: string;
  target_id: string;
}

export interface ScopedCopilotRun {
  id: string;
  scope_id: string;
  scope_name: string;
  persona_id: string | null;
  prompt: string;
  status: ScopedCopilotRunStatus;
  created_at: string;
  completed_at: string | null;
  output_summary: string | null;
  citations: ScopedCopilotCitation[];
  error_message: string | null;
  output_markdown?: string | null;
}

export interface CreateScopedCopilotRunPayload {
  query: string;
  scope: Record<string, unknown>;
}

export interface GovernanceCopilotResponse {
  answer: string;
  [key: string]: unknown;
}
