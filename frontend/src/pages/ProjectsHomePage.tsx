import { Link, useNavigate } from "react-router-dom";
import { useProjects } from "@/api/projectHooks";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { MotionItem, MotionStagger } from "@/components/common/motion";
import type { Project } from "@/api/types";

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active:
      "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200/70 dark:bg-emerald-900/20 dark:text-emerald-400 dark:ring-emerald-900/50",
    setup:
      "bg-amber-50 text-amber-700 ring-1 ring-amber-200/70 dark:bg-amber-900/20 dark:text-amber-400 dark:ring-amber-900/50",
    error: "bg-red-50 text-red-700 ring-1 ring-red-200/70 dark:bg-red-900/20 dark:text-red-400 dark:ring-red-900/50",
  };
  return (
    <span
      className={`badge ${styles[status] ?? styles.setup}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {status.charAt(0).toUpperCase() + status.slice(1)}
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
      className="card-interactive group relative overflow-hidden p-6"
    >
      <div className="absolute inset-x-0 top-0 h-1 bg-brand-gradient opacity-80" />
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

      <div className="mt-5 grid grid-cols-3 gap-3">
        <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/50">
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Identities
          </p>
          <AnimatedNumber
            value={project.identity_count}
            className="mt-0.5 block text-lg font-bold tabular-nums text-slate-900 dark:text-white"
          />
        </div>
        <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/50">
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Risk Score
          </p>
          <AnimatedNumber
            value={project.risk_score}
            decimals={1}
            className="mt-0.5 block text-lg font-bold tabular-nums text-slate-900 dark:text-white"
          />
        </div>
        <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/50">
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Last Scan
          </p>
          <p className="mt-0.5 text-sm font-medium text-slate-600 dark:text-slate-300">
            {relativeTime(project.last_scan_at)}
          </p>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-brand-600 transition-transform group-hover:translate-x-0.5 dark:text-brand-400">
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
      className="card-interactive group flex min-h-[214px] flex-col items-center justify-center border-dashed border-slate-300 bg-white/70 p-6 text-center hover:border-brand-300 hover:bg-brand-50/50 dark:border-slate-700 dark:bg-slate-900/60 dark:hover:border-brand-800 dark:hover:bg-brand-950/30"
    >
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-glow transition-transform group-hover:scale-105">
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
      <p className="mt-1 max-w-[12rem] text-xs leading-relaxed text-slate-400 dark:text-slate-500">
        Connect a new Entra ID tenant
      </p>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="card p-6">
      <div className="flex justify-between">
        <div className="skeleton h-5 w-1/2" />
        <div className="skeleton h-5 w-16 rounded-full" />
      </div>
      <div className="skeleton mt-2 h-4 w-2/3" />
      <div className="mt-5 grid grid-cols-3 gap-4">
        <div className="skeleton h-10" />
        <div className="skeleton h-10" />
        <div className="skeleton h-10" />
      </div>
    </div>
  );
}

export function ProjectsHomePage() {
  const { data: projects, isLoading, isError } = useProjects();

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
        <p className="eyebrow">Tenant Workspaces</p>
        <h1 className="page-title mt-1">Projects</h1>
        <p className="page-subtitle">
          Manage premium Entra ID tenant connections and analysis workspaces.
        </p>
        </div>
        <Link to="/docs" className="btn-secondary">
          Documentation
        </Link>
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
        <MotionStagger className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {projects?.map((p) => (
            <MotionItem key={p.id}>
              <ProjectCard project={p} />
            </MotionItem>
          ))}
          <MotionItem>
            <NewProjectCard />
          </MotionItem>
        </MotionStagger>
      )}
    </div>
  );
}
