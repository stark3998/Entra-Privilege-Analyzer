// frontend/src/components/common/AINarrativeCard.tsx
import clsx from "clsx";

interface AINarrativeCardProps {
  /** Card title displayed in header. */
  title: string;
  /** AI-generated narrative content. Paragraphs split by newlines. */
  content: string | null;
  /** Whether the narrative is loading. */
  isLoading: boolean;
  /** Optional callback to refresh the narrative. */
  onRefresh?: () => void;
  /** Whether a refresh is currently in progress. */
  isRefreshing?: boolean;
}

/**
 * Card for displaying AI-generated narrative content.
 * Includes a sparkle icon, paragraph rendering, refresh button,
 * loading skeleton, and empty state.
 *
 * Usage:
 * ```tsx
 * <AINarrativeCard
 *   title="Executive Digest"
 *   content={narrative?.content ?? null}
 *   isLoading={isLoading}
 *   onRefresh={() => refresh()}
 *   isRefreshing={isRefreshing}
 * />
 * ```
 */
export function AINarrativeCard({
  title,
  content,
  isLoading,
  onRefresh,
  isRefreshing = false,
}: AINarrativeCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Sparkle icon */}
          <svg
            className="h-5 w-5 text-amber-500 dark:text-amber-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z"
            />
          </svg>
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
            {title}
          </h3>
        </div>

        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className={clsx(
              "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
              isRefreshing
                ? "cursor-not-allowed text-slate-400 dark:text-slate-600"
                : "text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200",
            )}
          >
            <svg
              className={clsx("h-3.5 w-3.5", isRefreshing && "animate-spin")}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            Refresh
          </button>
        )}
      </div>

      {/* Content */}
      <div className="mt-4">
        {isLoading ? (
          <div className="space-y-3">
            <div className="h-4 w-full animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
            <div className="h-4 w-5/6 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
            <div className="h-4 w-4/6 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
            <div className="h-4 w-full animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
            <div className="h-4 w-3/4 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
          </div>
        ) : content ? (
          <div className="space-y-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
            {content.split("\n").filter(Boolean).map((paragraph, idx) => (
              <p key={idx}>{paragraph}</p>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-400 dark:text-slate-500">
            AI narrative not available
          </p>
        )}
      </div>
    </div>
  );
}
