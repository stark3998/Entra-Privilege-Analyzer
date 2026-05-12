// frontend/src/api/hooks.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getApiClient } from "./client";
import { useTenant } from "@/store/tenantContext";
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
  const { tenantId } = useTenant();
  const client = getApiClient();

  const queryString = new URLSearchParams();
  if (params.type) queryString.set("type", params.type);
  if (params.search) queryString.set("search", params.search);
  queryString.set("page", String(params.page ?? 1));
  queryString.set("size", String(params.size ?? 50));

  return useQuery({
    queryKey: ["identities", tenantId, params],
    queryFn: () =>
      client.get<PaginatedResponse<IdentityProfile>>(
        `/api/tenants/${tenantId}/identities?${queryString}`,
      ),
  });
}

/**
 * Fetch a single identity profile by ID for the active tenant.
 */
export function useIdentityDetail(identityId: string) {
  const { tenantId } = useTenant();
  const client = getApiClient();

  return useQuery({
    queryKey: ["identity", tenantId, identityId],
    queryFn: () =>
      client.get<IdentityProfile>(
        `/api/tenants/${tenantId}/identities/${identityId}`,
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
  const { tenantId } = useTenant();
  const client = getApiClient();

  return useQuery({
    queryKey: ["actions", tenantId, identityId, params],
    queryFn: () =>
      client.get<PaginatedResponse<ActionEvent>>(
        `/api/tenants/${tenantId}/identities/${identityId}/actions?page=${params.page ?? 1}&size=${params.size ?? 50}`,
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
  const { tenantId } = useTenant();
  const client = getApiClient();

  const queryString = new URLSearchParams();
  if (params.type) queryString.set("type", params.type);
  if (params.search) queryString.set("search", params.search);
  if (params.sort) queryString.set("sort", params.sort);
  queryString.set("page", String(params.page ?? 1));
  queryString.set("size", String(params.size ?? 20));

  return useQuery({
    queryKey: ["recommendations", tenantId, params],
    queryFn: () =>
      client.get<PaginatedResponse<RoleRecommendation>>(
        `/api/tenants/${tenantId}/recommendations?${queryString}`,
      ),
  });
}

/**
 * Fetch a single role recommendation by identity ID.
 */
export function useRecommendationDetail(identityId: string) {
  const { tenantId } = useTenant();
  const client = getApiClient();

  return useQuery({
    queryKey: ["recommendation", tenantId, identityId],
    queryFn: () =>
      client.get<RoleRecommendation>(
        `/api/tenants/${tenantId}/recommendations/${identityId}`,
      ),
    enabled: !!identityId,
  });
}

/**
 * Mutation hook to trigger recommendation computation for all identities.
 * Invalidates the recommendations query cache on success.
 */
export function useComputeRecommendations() {
  const { tenantId } = useTenant();
  const client = getApiClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      client.post<{ status: string }>(
        `/api/tenants/${tenantId}/recommendations/compute`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations", tenantId] });
    },
  });
}

/**
 * Fetch an IaC export for a specific identity in the given format.
 * Disabled by default — call `refetch()` to trigger on demand.
 */
export function useExport(identityId: string, format: ExportFormat) {
  const { tenantId } = useTenant();
  const client = getApiClient();

  return useQuery({
    queryKey: ["export", tenantId, identityId, format],
    queryFn: () =>
      client.get<ExportResult>(
        `/api/tenants/${tenantId}/exports/${identityId}?format=${format}`,
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
  const { tenantId } = useTenant();
  const client = getApiClient();

  const queryString = new URLSearchParams();
  if (params.severity) queryString.set("severity", params.severity);
  if (params.status) queryString.set("status", params.status);
  if (params.search) queryString.set("search", params.search);
  queryString.set("page", String(params.page ?? 1));
  queryString.set("size", String(params.size ?? 20));

  return useQuery({
    queryKey: ["driftAlerts", tenantId, params],
    queryFn: () =>
      client.get<PaginatedResponse<DriftAlert>>(
        `/api/tenants/${tenantId}/drift?${queryString}`,
      ),
  });
}

/**
 * Fetch a single drift alert by ID.
 */
export function useDriftAlertDetail(alertId: string) {
  const { tenantId } = useTenant();
  const client = getApiClient();

  return useQuery({
    queryKey: ["driftAlert", tenantId, alertId],
    queryFn: () =>
      client.get<DriftAlert>(
        `/api/tenants/${tenantId}/drift/${alertId}`,
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
  const { tenantId } = useTenant();
  const client = getApiClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ alertId, status, notes }: UpdateDriftAlertPayload) =>
      client.patch<DriftAlert>(
        `/api/tenants/${tenantId}/drift/${alertId}`,
        { status, notes },
      ),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["driftAlerts", tenantId] });
      queryClient.invalidateQueries({
        queryKey: ["driftAlert", tenantId, variables.alertId],
      });
    },
  });
}

/**
 * Mutation hook to trigger drift detection for all identities.
 * Invalidates drift alert queries on success.
 */
export function useDetectDrift() {
  const { tenantId } = useTenant();
  const client = getApiClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      client.post<{ status: string }>(
        `/api/tenants/${tenantId}/drift/detect`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["driftAlerts", tenantId] });
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
  const { tenantId } = useTenant();
  const client = getApiClient();

  const queryString = new URLSearchParams();
  if (params.type) queryString.set("type", params.type);
  if (params.priority) queryString.set("priority", params.priority);
  queryString.set("page", String(params.page ?? 1));
  queryString.set("size", String(params.size ?? 20));

  return useQuery({
    queryKey: ["violations", tenantId, params],
    queryFn: () =>
      client.get<PaginatedResponse<BestPracticeViolation>>(
        `/api/tenants/${tenantId}/best-practices/violations?${queryString}`,
      ),
  });
}

/**
 * Fetch a single best practice violation by ID.
 */
export function useViolationDetail(violationId: string) {
  const { tenantId } = useTenant();
  const client = getApiClient();

  return useQuery({
    queryKey: ["violation", tenantId, violationId],
    queryFn: () =>
      client.get<BestPracticeViolation>(
        `/api/tenants/${tenantId}/best-practices/violations/${violationId}`,
      ),
    enabled: !!violationId,
  });
}

/**
 * Fetch the best practice compliance summary for the active tenant.
 */
export function useBestPracticeSummary() {
  const { tenantId } = useTenant();
  const client = getApiClient();

  return useQuery({
    queryKey: ["bestPracticeSummary", tenantId],
    queryFn: () =>
      client.get<BestPracticeSummary>(
        `/api/tenants/${tenantId}/best-practices/summary`,
      ),
  });
}

/**
 * Mutation hook to trigger best practice evaluation for all identities.
 * Invalidates violations and summary queries on success.
 */
export function useEvaluateBestPractices() {
  const { tenantId } = useTenant();
  const client = getApiClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      client.post<{ status: string }>(
        `/api/tenants/${tenantId}/best-practices/evaluate`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["violations", tenantId] });
      queryClient.invalidateQueries({
        queryKey: ["bestPracticeSummary", tenantId],
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
  const { tenantId } = useTenant();
  const client = getApiClient();

  return useQuery({
    queryKey: ["dashboardSummary", tenantId],
    queryFn: () =>
      client.get<DashboardSummary>(
        `/api/tenants/${tenantId}/dashboard/summary`,
      ),
  });
}

/**
 * Fetch 30-day trend data for risk score, drift alerts, and actions.
 */
export function useDashboardTrends() {
  const { tenantId } = useTenant();
  const client = getApiClient();

  return useQuery({
    queryKey: ["dashboardTrends", tenantId],
    queryFn: () =>
      client.get<DashboardTrends>(
        `/api/tenants/${tenantId}/dashboard/trends`,
      ),
  });
}

/**
 * Fetch the AI-generated executive narrative for the active tenant.
 */
export function useExecutiveNarrative() {
  const { tenantId } = useTenant();
  const client = getApiClient();

  return useQuery({
    queryKey: ["executiveNarrative", tenantId],
    queryFn: () =>
      client.get<Narrative>(
        `/api/tenants/${tenantId}/dashboard/narrative`,
      ),
  });
}

/**
 * Mutation hook to refresh the AI-generated executive narrative.
 * Invalidates the narrative query on success.
 */
export function useRefreshNarrative() {
  const { tenantId } = useTenant();
  const client = getApiClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      client.post<Narrative>(
        `/api/tenants/${tenantId}/dashboard/narrative/refresh`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["executiveNarrative", tenantId],
      });
    },
  });
}

// --- Phase 7: Settings & Reports ---

/**
 * Fetch the tenant settings (sync schedule, baseline window).
 */
export function useTenantSettings() {
  const { tenantId } = useTenant();
  const client = getApiClient();

  return useQuery({
    queryKey: ["tenantSettings", tenantId],
    queryFn: () =>
      client.get<TenantSettings>(
        `/api/tenants/${tenantId}/settings`,
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
  const { tenantId } = useTenant();
  const client = getApiClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UpdateSettingsPayload) =>
      client.put<TenantSettings>(
        `/api/tenants/${tenantId}/settings`,
        payload,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["tenantSettings", tenantId],
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
  const { tenantId } = useTenant();
  const client = getApiClient();

  return useQuery({
    queryKey: ["downloadReport", tenantId, format],
    queryFn: () =>
      client.getBlob(
        `/api/tenants/${tenantId}/reports/executive?format=${format}`,
      ),
    enabled: false,
  });
}
