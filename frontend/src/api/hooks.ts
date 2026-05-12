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
