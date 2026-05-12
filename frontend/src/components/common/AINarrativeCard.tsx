import clsx from "clsx";
import { Tooltip } from "./Tooltip";

interface AINarrativeCardProps {
  title: string;
  content: string | null;
  isLoading: boolean;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function AINarrativeCard({
  title,
  content,
  isLoading,
  onRefresh,
  isRefreshing = false,
}: AINarrativeCardProps) {
  return (
    <div className="card overflow-hidden">
      {/* Accent header bar */}
      <div className="h-1 bg-gradient-to-r from-amber-400 via-orange-400 to-rose-400" />

      <div className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-50 dark:bg-amber-900/20">
              <svg
                className="h-4 w-4 text-amber-500 dark:text-amber-400"
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round" strokeLinejoin="round"
                  d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z"
                />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                {title}
              </h3>
              <p className="text-[10px] text-slate-400 dark:text-slate-500">
                AI-generated via Microsoft Foundry
              </p>
            </div>
          </div>

          {onRefresh && (
            <Tooltip content="Regenerate AI narrative">
              <button
                type="button"
                onClick={onRefresh}
                disabled={isRefreshing}
                aria-label="Refresh AI narrative"
                className={clsx(
                  "flex h-8 w-8 items-center justify-center rounded-lg transition-all",
                  isRefreshing
                    ? "cursor-not-allowed text-slate-300 dark:text-slate-600"
                    : "text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300",
                )}
              >
                <svg
                  className={clsx("h-4 w-4", isRefreshing && "animate-spin")}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                >
                  <path
                    strokeLinecap="round" strokeLinejoin="round"
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
              </button>
            </Tooltip>
          )}
        </div>

        {/* Content */}
        <div className="mt-4">
          {isLoading ? (
            <div className="space-y-3">
              <div className="h-4 w-full animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
              <div className="h-4 w-5/6 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
              <div className="h-4 w-4/6 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
              <div className="h-4 w-full animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
            </div>
          ) : content ? (
            <div className="space-y-2.5 text-[13px] leading-relaxed text-slate-600 dark:text-slate-400">
              {content.split("\n").filter(Boolean).map((paragraph, idx) => (
                <p key={idx}>{paragraph}</p>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center py-6 text-center">
              <svg className="h-8 w-8 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
              <p className="mt-2 text-sm text-slate-400 dark:text-slate-500">
                AI narrative not available
              </p>
              <p className="text-xs text-slate-400 dark:text-slate-500">
                Click refresh to generate
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
