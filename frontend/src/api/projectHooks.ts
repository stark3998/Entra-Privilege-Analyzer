import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getApiClient } from "./client";
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

export function useLatestScan(projectId: string) {
  const client = getApiClient();
  return useQuery({
    queryKey: ["latestScan", projectId],
    queryFn: () =>
      client.get<ScanRecord>(`/api/projects/${projectId}/scans/latest`),
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
