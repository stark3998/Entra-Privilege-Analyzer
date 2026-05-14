import { useNavigate } from "react-router-dom";
import { useProjects } from "@/api/projectHooks";
import type { Project } from "@/api/types";

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active:
      "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400",
    setup:
      "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400",
    error: "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400",
  };
  return (
    <span
      className={`badge ${styles[status] ?? styles.setup}`}
    >
      {status}
    </span>
  );
}

function relativeTime(iso: string | null): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function ProjectCard({ project }: { project: Project }) {
  const navigate = useNavigate();

  return (
    <div
      onClick={() => navigate(`/projects/${project.id}/dashboard`)}
      className="card-interactive p-6"
    >
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-base font-semibold text-slate-900 dark:text-white">
            {project.name}
          </h3>
          <p className="mt-1 truncate text-sm text-slate-500 dark:text-slate-400">
            {project.target_tenant_name}
          </p>
        </div>
        <StatusBadge status={project.status} />
      </div>

      <div className="mt-5 grid grid-cols-3 gap-4">
        <div>
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Identities
          </p>
          <p className="mt-0.5 text-lg font-bold tabular-nums text-slate-900 dark:text-white">
            {project.identity_count.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Risk Score
          </p>
          <p className="mt-0.5 text-lg font-bold tabular-nums text-slate-900 dark:text-white">
            {project.risk_score.toFixed(1)}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Last Scan
          </p>
          <p className="mt-0.5 text-sm font-medium text-slate-600 dark:text-slate-300">
            {relativeTime(project.last_scan_at)}
          </p>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-1 text-xs font-medium text-brand-600 dark:text-brand-400">
        <span>Open project</span>
        <svg
          className="h-3 w-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 5l7 7-7 7"
          />
        </svg>
      </div>
    </div>
  );
}

function NewProjectCard() {
  const navigate = useNavigate();

  return (
    <div
      onClick={() => navigate("/projects/new")}
      className="flex min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-white/50 transition-all hover:border-brand-300 hover:bg-brand-50/50 dark:border-slate-700 dark:bg-slate-900/50 dark:hover:border-brand-700 dark:hover:bg-brand-950/30"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-600 dark:bg-brand-900/30 dark:text-brand-400">
        <svg
          className="h-6 w-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 4v16m8-8H4"
          />
        </svg>
      </div>
      <p className="mt-3 text-sm font-semibold text-slate-700 dark:text-slate-300">
        New Project
      </p>
      <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
        Connect a new Entra ID tenant
      </p>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="card animate-pulse p-6">
      <div className="flex justify-between">
        <div className="h-5 w-1/2 rounded bg-slate-100 dark:bg-slate-800" />
        <div className="h-5 w-16 rounded-full bg-slate-100 dark:bg-slate-800" />
      </div>
      <div className="mt-2 h-4 w-2/3 rounded bg-slate-100 dark:bg-slate-800" />
      <div className="mt-5 grid grid-cols-3 gap-4">
        <div className="h-10 rounded bg-slate-100 dark:bg-slate-800" />
        <div className="h-10 rounded bg-slate-100 dark:bg-slate-800" />
        <div className="h-10 rounded bg-slate-100 dark:bg-slate-800" />
      </div>
    </div>
  );
}

export function ProjectsHomePage() {
  const { data: projects, isLoading, isError } = useProjects();

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <div>
        <h1 className="page-title">Projects</h1>
        <p className="page-subtitle">
          Manage your Entra ID tenant connections
        </p>
      </div>

      {isError && (
        <div className="card border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          Failed to load projects. Please try again later.
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {projects?.map((p) => <ProjectCard key={p.id} project={p} />)}
          <NewProjectCard />
        </div>
      )}
    </div>
  );
}
