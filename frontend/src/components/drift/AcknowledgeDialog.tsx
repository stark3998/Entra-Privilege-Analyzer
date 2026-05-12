// frontend/src/components/drift/AcknowledgeDialog.tsx
import { useState } from "react";
import type { DriftAlert, DriftStatus } from "@/api/types";
import { SeverityBadge } from "@/components/common/SeverityBadge";

interface AcknowledgeDialogProps {
  alert: DriftAlert;
  targetStatus: DriftStatus;
  onConfirm: (notes: string) => void;
  onCancel: () => void;
  isPending: boolean;
}

const STATUS_LABELS: Record<DriftStatus, string> = {
  open: "Reopen",
  acknowledged: "Acknowledge",
  escalated: "Escalate",
  resolved: "Resolve",
};

/**
 * Modal confirmation dialog for updating a drift alert's status.
 * Includes an alert summary and optional notes field.
 */
export function AcknowledgeDialog({
  alert,
  targetStatus,
  onConfirm,
  onCancel,
  isPending,
}: AcknowledgeDialogProps) {
  const [notes, setNotes] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 dark:bg-black/70"
        onClick={onCancel}
      />

      <div className="animate-scale-in relative z-10 mx-4 w-full max-w-md rounded-2xl border border-slate-200/80 bg-white p-6 shadow-xl dark:border-slate-700/80 dark:bg-slate-900">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
          {STATUS_LABELS[targetStatus]} Alert
        </h2>

        {/* Alert summary */}
        <div className="mt-4 rounded-xl border border-slate-200/80 bg-slate-50 p-3 dark:border-slate-700/80 dark:bg-slate-800/60">
          <div className="flex items-center gap-2">
            <SeverityBadge severity={alert.severity} />
            <span className="text-sm font-medium text-slate-900 dark:text-white">
              {alert.identity_display_name}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            {alert.action}
          </p>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-500">
            {alert.details}
          </p>
        </div>

        {/* Notes input */}
        <div className="mt-4">
          <label
            htmlFor="dialog-notes"
            className="block text-sm font-medium text-slate-700 dark:text-slate-300"
          >
            Notes (optional)
          </label>
          <textarea
            id="dialog-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add any context or reason..."
            rows={3}
            className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500 dark:focus:border-brand-400 dark:focus:ring-brand-400"
          />
        </div>

        {/* Actions */}
        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isPending}
            className="btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(notes)}
            disabled={isPending}
            className="btn-primary"
          >
            {isPending && (
              <svg
                className="h-4 w-4 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            )}
            {STATUS_LABELS[targetStatus]}
          </button>
        </div>
      </div>
    </div>
  );
}
