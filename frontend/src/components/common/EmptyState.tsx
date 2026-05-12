// frontend/src/components/common/EmptyState.tsx
import type { ReactNode } from "react";

interface EmptyStateProps {
  /** Optional icon rendered above the title. */
  icon?: ReactNode;
  /** Primary heading text. */
  title: string;
  /** Optional description below the title. */
  description?: string;
  /** Optional action element (e.g. a button) rendered at the bottom. */
  action?: ReactNode;
}

/**
 * Centered empty-state card with icon, title, description, and optional action.
 */
export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center dark:border-slate-700 dark:bg-slate-900/50">
      {icon && (
        <div className="mb-4 text-slate-400 dark:text-slate-500">{icon}</div>
      )}
      <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
        {title}
      </h3>
      {description && (
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
