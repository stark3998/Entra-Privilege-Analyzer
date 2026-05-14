// frontend/src/api/hooks.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getApiClient } from "./client";
import { useProjectContext } from "@/store/projectContext";
import type {
  TenantInfo,
  IdentityType,
  IdentityProfile,
  PaginatedResponse,
  ActionEvent,
  RoleRecommendation,
  ExportFormat,
  ExportResult,
  DriftAlert,
  DriftSeverity,
  DriftStatus,
  BestPracticeViolation,
  BestPracticeSummary,
  ViolationType,
  ViolationPriority,
  DashboardSummary,
  DashboardTrends,
  Narrative,
  TenantSettings,
  AnalyticsData,
} from "./types";

/**
 * Fetch current tenant info from the backend.
 * Requires the ApiClient to have been initialized with a token provider.
 */
export function useTenantInfo() {
  const client = getApiClient();
  return useQuery({
    queryKey: ["tenant", "me"],
    queryFn: () => client.get<TenantInfo>("/api/tenants/me"),
  });
}

/** Parameters for the identities list query. */
interface IdentitiesParams {
  type?: IdentityType;
  search?: string;
  page?: number;
  size?: number;
}

/**
 * Fetch a paginated list of identities for the active tenant.
 * Supports filtering by identity type and search string.
 */
export function useIdentities(params: IdentitiesParams) {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  const queryString = new URLSearchParams();
  if (params.type) queryString.set("type", params.type);
  if (params.search) queryString.set("search", params.search);
  queryString.set("page", String(params.page ?? 1));
  queryString.set("size", String(params.size ?? 50));

  return useQuery({
    queryKey: ["identities", projectId, params],
    queryFn: () =>
      client.get<PaginatedResponse<IdentityProfile>>(
        `/api/projects/${projectId}/identities?${queryString}`,
      ),
  });
}

/**
 * Fetch a single identity profile by ID for the active tenant.
 */
export function useIdentityDetail(identityId: string) {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  return useQuery({
    queryKey: ["identity", projectId, identityId],
    queryFn: () =>
      client.get<IdentityProfile>(
        `/api/projects/${projectId}/identities/${identityId}`,
      ),
    enabled: !!identityId,
  });
}

/** Parameters for the actions list query. */
interface ActionsParams {
  page?: number;
  size?: number;
}

/**
 * Fetch paginated action events for a specific identity.
 */
export function useActions(identityId: string, params: ActionsParams) {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  return useQuery({
    queryKey: ["actions", projectId, identityId, params],
    queryFn: () =>
      client.get<PaginatedResponse<ActionEvent>>(
        `/api/projects/${projectId}/identities/${identityId}/actions?page=${params.page ?? 1}&size=${params.size ?? 50}`,
      ),
    enabled: !!identityId,
  });
}

// --- Phase 3: Role Recommendations ---

/** Parameters for the recommendations list query. */
interface RecommendationsParams {
  type?: IdentityType;
  search?: string;
  sort?: string;
  page?: number;
  size?: number;
}

/**
 * Fetch a paginated list of role recommendations for the active tenant.
 * Supports filtering by identity type, search string, and sort order.
 */
export function useRecommendations(params: RecommendationsParams) {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  const queryString = new URLSearchParams();
  if (params.type) queryString.set("type", params.type);
  if (params.search) queryString.set("search", params.search);
  if (params.sort) queryString.set("sort", params.sort);
  queryString.set("page", String(params.page ?? 1));
  queryString.set("size", String(params.size ?? 20));

  return useQuery({
    queryKey: ["recommendations", projectId, params],
    queryFn: () =>
      client.get<PaginatedResponse<RoleRecommendation>>(
        `/api/projects/${projectId}/recommendations?${queryString}`,
      ),
  });
}

/**
 * Fetch a single role recommendation by identity ID.
 */
export function useRecommendationDetail(identityId: string) {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  return useQuery({
    queryKey: ["recommendation", projectId, identityId],
    queryFn: () =>
      client.get<RoleRecommendation>(
        `/api/projects/${projectId}/recommendations/${identityId}`,
      ),
    enabled: !!identityId,
  });
}

/**
 * Mutation hook to trigger recommendation computation for all identities.
 * Invalidates the recommendations query cache on success.
 */
export function useComputeRecommendations() {
  const { projectId } = useProjectContext();
  const client = getApiClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      client.post<{ status: string }>(
        `/api/projects/${projectId}/recommendations/compute`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations", projectId] });
    },
  });
}

/**
 * Fetch an IaC export for a specific identity in the given format.
 * Disabled by default — call `refetch()` to trigger on demand.
 */
export function useExport(identityId: string, format: ExportFormat) {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  return useQuery({
    queryKey: ["export", projectId, identityId, format],
    queryFn: () =>
      client.get<ExportResult>(
        `/api/projects/${projectId}/exports/${identityId}?format=${format}`,
      ),
    enabled: false,
  });
}

// --- Phase 4: Drift Detection ---

/** Parameters for the drift alerts list query. */
interface DriftAlertsParams {
  severity?: DriftSeverity;
  status?: DriftStatus;
  search?: string;
  page?: number;
  size?: number;
}

/**
 * Fetch a paginated list of drift alerts for the active tenant.
 * Supports filtering by severity, status, and search string.
 */
export function useDriftAlerts(params: DriftAlertsParams) {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  const queryString = new URLSearchParams();
  if (params.severity) queryString.set("severity", params.severity);
  if (params.status) queryString.set("status", params.status);
  if (params.search) queryString.set("search", params.search);
  queryString.set("page", String(params.page ?? 1));
  queryString.set("size", String(params.size ?? 20));

  return useQuery({
    queryKey: ["driftAlerts", projectId, params],
    queryFn: () =>
      client.get<PaginatedResponse<DriftAlert>>(
        `/api/projects/${projectId}/drift-alerts?${queryString}`,
      ),
  });
}

/**
 * Fetch a single drift alert by ID.
 */
export function useDriftAlertDetail(alertId: string) {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  return useQuery({
    queryKey: ["driftAlert", projectId, alertId],
    queryFn: () =>
      client.get<DriftAlert>(
        `/api/projects/${projectId}/drift-alerts/${alertId}`,
      ),
    enabled: !!alertId,
  });
}

/** Payload for updating a drift alert status. */
interface UpdateDriftAlertPayload {
  alertId: string;
  status: DriftStatus;
  notes?: string;
}

/**
 * Mutation hook to update a drift alert's status (acknowledge, escalate, resolve).
 * Invalidates drift alert queries on success.
 */
export function useUpdateDriftAlert() {
  const { projectId } = useProjectContext();
  const client = getApiClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ alertId, status, notes }: UpdateDriftAlertPayload) =>
      client.patch<DriftAlert>(
        `/api/projects/${projectId}/drift-alerts/${alertId}`,
        { status, notes },
      ),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["driftAlerts", projectId] });
      queryClient.invalidateQueries({
        queryKey: ["driftAlert", projectId, variables.alertId],
      });
    },
  });
}

/**
 * Mutation hook to trigger drift detection for all identities.
 * Invalidates drift alert queries on success.
 */
export function useDetectDrift() {
  const { projectId } = useProjectContext();
  const client = getApiClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      client.post<{ status: string }>(
        `/api/projects/${projectId}/drift-alerts/detect`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["driftAlerts", projectId] });
    },
  });
}

// --- Phase 5: Best Practices ---

/** Parameters for the violations list query. */
interface ViolationsParams {
  type?: ViolationType;
  priority?: ViolationPriority;
  page?: number;
  size?: number;
}

/**
 * Fetch a paginated list of best practice violations for the active tenant.
 * Supports filtering by violation type and priority.
 */
export function useViolations(params: ViolationsParams) {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  const queryString = new URLSearchParams();
  if (params.type) queryString.set("type", params.type);
  if (params.priority) queryString.set("priority", params.priority);
  queryString.set("page", String(params.page ?? 1));
  queryString.set("size", String(params.size ?? 20));

  return useQuery({
    queryKey: ["violations", projectId, params],
    queryFn: () =>
      client.get<PaginatedResponse<BestPracticeViolation>>(
        `/api/projects/${projectId}/best-practices?${queryString}`,
      ),
  });
}

/**
 * Fetch a single best practice violation by ID.
 */
export function useViolationDetail(violationId: string) {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  return useQuery({
    queryKey: ["violation", projectId, violationId],
    queryFn: () =>
      client.get<BestPracticeViolation>(
        `/api/projects/${projectId}/best-practices/${violationId}`,
      ),
    enabled: !!violationId,
  });
}

/**
 * Fetch the best practice compliance summary for the active tenant.
 */
export function useBestPracticeSummary() {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  return useQuery({
    queryKey: ["bestPracticeSummary", projectId],
    queryFn: () =>
      client.get<BestPracticeSummary>(
        `/api/projects/${projectId}/best-practices/summary`,
      ),
  });
}

/**
 * Mutation hook to trigger best practice evaluation for all identities.
 * Invalidates violations and summary queries on success.
 */
export function useEvaluateBestPractices() {
  const { projectId } = useProjectContext();
  const client = getApiClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      client.post<{ status: string }>(
        `/api/projects/${projectId}/best-practices/evaluate`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["violations", projectId] });
      queryClient.invalidateQueries({
        queryKey: ["bestPracticeSummary", projectId],
      });
    },
  });
}

// --- Phase 6: Executive Dashboard ---

/**
 * Fetch the executive dashboard summary for the active tenant.
 * Includes identity counts, risk scores, drift alerts, and top risky identities.
 */
export function useDashboardSummary() {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  return useQuery({
    queryKey: ["dashboardSummary", projectId],
    queryFn: () =>
      client.get<DashboardSummary>(
        `/api/projects/${projectId}/dashboard`,
      ),
  });
}

/**
 * Fetch analytics data for the active project.
 * Supports variable time ranges (7d, 30d, 90d).
 */
export function useAnalytics(days: number = 30) {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  return useQuery({
    queryKey: ["analytics", projectId, days],
    queryFn: () =>
      client.get<AnalyticsData>(
        `/api/projects/${projectId}/analytics?days=${days}`,
      ),
  });
}

/**
 * Fetch 30-day trend data for risk score, drift alerts, and actions.
 */
export function useDashboardTrends() {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  return useQuery({
    queryKey: ["dashboardTrends", projectId],
    queryFn: () =>
      client.get<DashboardTrends>(
        `/api/projects/${projectId}/dashboard/trends`,
      ),
  });
}

/**
 * Fetch the AI-generated executive narrative for the active tenant.
 */
export function useExecutiveNarrative() {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  return useQuery({
    queryKey: ["executiveNarrative", projectId],
    queryFn: () =>
      client.get<Narrative>(
        `/api/projects/${projectId}/narratives/executive`,
      ),
  });
}

/**
 * Mutation hook to refresh the AI-generated executive narrative.
 * Invalidates the narrative query on success.
 */
export function useRefreshNarrative() {
  const { projectId } = useProjectContext();
  const client = getApiClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      client.post<Narrative>(
        `/api/projects/${projectId}/narratives/refresh`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["executiveNarrative", projectId],
      });
    },
  });
}

// --- Phase 7: Settings & Reports ---

/**
 * Fetch the tenant settings (sync schedule, baseline window).
 */
export function useTenantSettings() {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  return useQuery({
    queryKey: ["tenantSettings", projectId],
    queryFn: () =>
      client.get<TenantSettings>(
        `/api/projects/${projectId}/settings`,
      ),
  });
}

/** Payload for updating tenant settings. */
interface UpdateSettingsPayload {
  sync_schedule_hours: number;
  baseline_window_days: number;
}

/**
 * Mutation hook to update tenant settings.
 * Invalidates the tenant settings query on success.
 */
export function useUpdateTenantSettings() {
  const { projectId } = useProjectContext();
  const client = getApiClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UpdateSettingsPayload) =>
      client.put<TenantSettings>(
        `/api/projects/${projectId}/settings`,
        payload,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["tenantSettings", projectId],
      });
    },
  });
}

/**
 * Hook to download an executive report as PDF or PPTX.
 * Disabled by default -- call `refetch()` to trigger on demand.
 * Returns a Blob that can be saved as a file.
 */
export function useDownloadReport(format: "pdf" | "pptx") {
  const { projectId } = useProjectContext();
  const client = getApiClient();

  return useQuery({
    queryKey: ["downloadReport", projectId, format],
    queryFn: () =>
      client.getBlob(
        `/api/projects/${projectId}/reports/executive?format=${format}`,
      ),
    enabled: false,
  });
}
