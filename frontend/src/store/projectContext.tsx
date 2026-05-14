import {
  createContext,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import { useParams } from "react-router-dom";
import { useProject } from "@/api/projectHooks";
import { TenantProvider } from "@/store/tenantContext";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import type { Project } from "@/api/types";

interface ProjectContextValue {
  projectId: string;
  project: Project;
  tenantId: string;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const { projectId } = useParams<{ projectId: string }>();
  const { data: project, isLoading, isError } = useProject(projectId ?? "");

  const value = useMemo(
    () =>
      project
        ? {
            projectId: project.id,
            project,
            tenantId: project.target_tenant_id,
          }
        : null,
    [project],
  );

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <LoadingSpinner />
      </div>
    );
  }

  if (isError || !value) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="card max-w-md p-8 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-50 dark:bg-red-900/20">
            <svg
              className="h-6 w-6 text-red-600 dark:text-red-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
              />
            </svg>
          </div>
          <h2 className="mt-4 text-lg font-semibold text-slate-900 dark:text-white">
            Project Not Found
          </h2>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            The project you're looking for doesn't exist or you don't have
            access to it.
          </p>
          <a href="/projects" className="btn-primary mt-6 inline-flex">
            Back to Projects
          </a>
        </div>
      </div>
    );
  }

  return (
    <ProjectContext.Provider value={value}>
      <TenantProvider
        tenantId={value.tenantId}
        tenantName={value.project.target_tenant_name}
      >
        {children}
      </TenantProvider>
    </ProjectContext.Provider>
  );
}

export function useProjectContext(): ProjectContextValue {
  const ctx = useContext(ProjectContext);
  if (!ctx) {
    throw new Error("useProjectContext must be used within a ProjectProvider");
  }
  return ctx;
}
