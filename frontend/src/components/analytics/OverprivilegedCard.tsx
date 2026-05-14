import { useNavigate } from "react-router-dom";

interface OverprivilegedCardProps {
  count: number;
}

export function OverprivilegedCard({ count }: OverprivilegedCardProps) {
  const navigate = useNavigate();

  return (
    <div
      onClick={() => navigate("../recommendations")}
      className="card-interactive cursor-pointer p-6"
    >
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        Overprivileged Identities
      </p>
      <p className="mt-2 text-3xl font-bold tabular-nums text-slate-900 dark:text-white">
        {count.toLocaleString()}
      </p>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        Identities with &gt;30% permission reduction possible
      </p>
      <div className="mt-4 flex items-center gap-1 text-xs font-medium text-brand-600 dark:text-brand-400">
        <span>View recommendations</span>
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
