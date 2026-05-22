import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError, getApiClient, type ServerSentEventMessage } from "./client";
import type {
  Project,
  CreateProjectPayload,
  UpdateProjectPayload,
  PermissionValidationResult,
  ProjectMember,
  ProjectMembersResponse,
  InviteMemberPayload,
  ScanRecord,
  PaginatedResponse,
  DelegatedPermissionsCheck,
  ScanStreamEvent,
  PollScanEventsResponse,
} from "./types";

export function useProjects() {
  const client = getApiClient();
  return useQuery({
    queryKey: ["projects"],
    queryFn: () => client.get<Project[]>("/api/projects"),
  });
}

export function useProject(projectId: string) {
  const client = getApiClient();
  return useQuery({
    queryKey: ["project", projectId],
    queryFn: () => client.get<Project>(`/api/projects/${projectId}`),
    enabled: !!projectId,
  });
}

export function useCreateProject() {
  const client = getApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateProjectPayload) =>
      client.post<Project>("/api/projects", payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useUpdateProject(projectId: string) {
  const client = getApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpdateProjectPayload) =>
      client.put<Project>(`/api/projects/${projectId}`, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}

export function useDeleteProject(projectId: string) {
  const client = getApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => client.delete<void>(`/api/projects/${projectId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useValidatePermissions(projectId: string) {
  const client = getApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      client.post<PermissionValidationResult>(
        `/api/projects/${projectId}/validate-permissions`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}

export function useProjectMembers(projectId: string) {
  const client = getApiClient();
  return useQuery({
    queryKey: ["projectMembers", projectId],
    queryFn: () =>
      client.get<ProjectMembersResponse>(`/api/projects/${projectId}/members`),
    enabled: !!projectId,
  });
}

export function useInviteMember(projectId: string) {
  const client = getApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: InviteMemberPayload) =>
      client.post<ProjectMember>(
        `/api/projects/${projectId}/members`,
        payload,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["projectMembers", projectId],
      });
    },
  });
}

export function useUpdateMemberRole(projectId: string) {
  const client = getApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: string }) =>
      client.put<ProjectMember>(
        `/api/projects/${projectId}/members/${memberId}`,
        { role },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["projectMembers", projectId],
      });
    },
  });
}

export function useRemoveMember(projectId: string) {
  const client = getApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (memberId: string) =>
      client.delete<void>(
        `/api/projects/${projectId}/members/${memberId}`,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["projectMembers", projectId],
      });
    },
  });
}

interface ScanHistoryParams {
  page?: number;
  size?: number;
}

export function useScanHistory(projectId: string, params: ScanHistoryParams) {
  const client = getApiClient();
  return useQuery({
    queryKey: ["scanHistory", projectId, params],
    queryFn: () =>
      client.get<PaginatedResponse<ScanRecord>>(
        `/api/projects/${projectId}/scans?page=${params.page ?? 1}&size=${params.size ?? 20}`,
      ),
    enabled: !!projectId,
  });
}

export function useScanLogs(
  projectId: string,
  scanId: string,
  params: { page?: number; size?: number } = {},
) {
  const client = getApiClient();
  return useQuery({
    queryKey: ["scanLogs", projectId, scanId, params],
    queryFn: () =>
      client.get<PaginatedResponse<ScanStreamEvent>>(
        `/api/projects/${projectId}/scans/${scanId}/logs?page=${params.page ?? 1}&size=${params.size ?? 500}`,
      ),
    enabled: !!projectId && !!scanId,
  });
}

export function useLatestScan(projectId: string) {
  const client = getApiClient();
  return useQuery({
    queryKey: ["latestScan", projectId],
    queryFn: async () => {
      try {
        return await client.get<ScanRecord>(`/api/projects/${projectId}/scans/latest`);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          return null;
        }
        throw error;
      }
    },
    enabled: !!projectId,
    retry: false,
  });
}

export function useTriggerScan(projectId: string) {
  const client = getApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      full = false,
      authMode = "app",
    }: {
      full?: boolean;
      authMode?: "app" | "delegated";
    } = {}) =>
      client.post<{ scan_id: string; status: string; auth_mode: string }>(
        `/api/projects/${projectId}/scans/trigger?full=${full}&auth_mode=${authMode}`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["scanHistory", projectId],
      });
      queryClient.invalidateQueries({ queryKey: ["latestScan", projectId] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useCancelScan(projectId: string) {
  const client = getApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scanId: string) =>
      client.post<{ scan_id: string; status: string; message: string }>(
        `/api/projects/${projectId}/scans/${scanId}/cancel`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["scanHistory", projectId],
      });
      queryClient.invalidateQueries({ queryKey: ["latestScan", projectId] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}

export function useResumeScan(projectId: string) {
  const client = getApiClient();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scanId: string) =>
      client.post<{ scan_id: string; status: string; auth_mode: string; resumed_from: string }>(
        `/api/projects/${projectId}/scans/${scanId}/resume`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["scanHistory", projectId],
      });
      queryClient.invalidateQueries({ queryKey: ["latestScan", projectId] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useDelegatedPermissionsCheck(projectId: string, enabled = false) {
  const client = getApiClient();
  return useQuery({
    queryKey: ["delegatedPermissions", projectId],
    queryFn: () =>
      client.get<DelegatedPermissionsCheck>(
        `/api/projects/${projectId}/scans/delegated-permissions-check`,
      ),
    enabled: !!projectId && enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

export function streamScanEvents(
  projectId: string,
  scanId: string | null,
  onMessage: (message: ServerSentEventMessage<ScanStreamEvent>) => void,
  signal?: AbortSignal,
) {
  const client = getApiClient();
  const query = scanId ? `?scan_id=${encodeURIComponent(scanId)}` : "";
  return client.stream<ScanStreamEvent>(
    `/api/projects/${projectId}/scans/events${query}`,
    onMessage,
    signal,
  );
}

export async function pollScanEvents(
  projectId: string,
  scanId: string | null,
  afterCursor: string | null,
): Promise<PollScanEventsResponse> {
  const client = getApiClient();
  const params = new URLSearchParams();
  if (scanId) params.set("scan_id", scanId);
  if (afterCursor) params.set("after", afterCursor);
  const qs = params.toString();
  const path = `/api/projects/${projectId}/scans/events/poll${qs ? `?${qs}` : ""}`;
  return client.get<PollScanEventsResponse>(path);
}

export interface FunctionLogsResponse {
  items: ScanStreamEvent[];
  cursor: string | null;
  available: boolean;
  error?: string;
  reason?: string;
}

export function useFunctionLogs(
  projectId: string,
  scanId: string | undefined,
  options: { after?: string | null; enabled?: boolean } = {},
) {
  const client = getApiClient();
  const after = options.after;
  return useQuery({
    queryKey: ["functionLogs", projectId, scanId, after],
    queryFn: () => {
      const params = new URLSearchParams();
      if (after) params.set("after", after);
      params.set("size", "100");
      const qs = params.toString();
      return client.get<FunctionLogsResponse>(
        `/api/projects/${projectId}/scans/${scanId}/function-logs${qs ? `?${qs}` : ""}`,
      );
    },
    enabled: !!projectId && !!scanId && (options.enabled !== false),
    refetchInterval: 10_000,
  });
}
