// frontend/src/pages/SettingsPage.tsx
import { useState, useEffect, useCallback } from "react";
import clsx from "clsx";
import { useTenantSettings, useUpdateTenantSettings } from "@/api/hooks";

const SYNC_SCHEDULE_OPTIONS: { label: string; value: number }[] = [
  { label: "Every 1 hour", value: 1 },
  { label: "Every 3 hours", value: 3 },
  { label: "Every 6 hours", value: 6 },
  { label: "Every 12 hours", value: 12 },
  { label: "Every 24 hours", value: 24 },
];

const BASELINE_WINDOW_OPTIONS: { label: string; value: number }[] = [
  { label: "7 days", value: 7 },
  { label: "14 days", value: 14 },
  { label: "30 days", value: 30 },
  { label: "60 days", value: 60 },
];

export function SettingsPage() {
  const { data: settings, isLoading, isError } = useTenantSettings();
  const updateMutation = useUpdateTenantSettings();

  const [syncHours, setSyncHours] = useState<number>(6);
  const [baselineDays, setBaselineDays] = useState<number>(30);
  const [showToast, setShowToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Seed form from fetched settings
  useEffect(() => {
    if (settings) {
      setSyncHours(settings.sync_schedule_hours);
      setBaselineDays(settings.baseline_window_days);
    }
  }, [settings]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!showToast) return;
    const timer = setTimeout(() => setShowToast(null), 4000);
    return () => clearTimeout(timer);
  }, [showToast]);

  const isDirty =
    settings !== undefined &&
    (syncHours !== settings.sync_schedule_hours ||
      baselineDays !== settings.baseline_window_days);

  const handleSave = useCallback(() => {
    updateMutation.mutate(
      { sync_schedule_hours: syncHours, baseline_window_days: baselineDays },
      {
        onSuccess: () => setShowToast({ type: "success", message: "Settings saved successfully." }),
        onError: (err) =>
          setShowToast({
            type: "error",
            message: err instanceof Error ? err.message : "Failed to save settings.",
          }),
      },
    );
  }, [updateMutation, syncHours, baselineDays]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          Settings
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Configure tenant-level sync and baseline settings
        </p>
      </div>

      {/* Toast */}
      {showToast && (
        <div
          className={clsx(
            "rounded-lg border p-3 text-sm",
            showToast.type === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400"
              : "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400",
          )}
        >
          {showToast.message}
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          Failed to load settings. Please try again later.
        </div>
      )}

      {/* Loading state */}
      {isLoading ? (
        <div className="animate-pulse space-y-4">
          <div className="h-10 w-2/3 rounded bg-slate-200 dark:bg-slate-700" />
          <div className="h-10 w-2/3 rounded bg-slate-200 dark:bg-slate-700" />
        </div>
      ) : settings ? (
        <div className="max-w-xl space-y-8">
          {/* Sync Configuration */}
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
              Sync Configuration
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Control how frequently data is synced from Entra ID.
            </p>

            <div className="mt-5 space-y-4">
              {/* Sync Schedule */}
              <div>
                <label
                  htmlFor="sync-schedule"
                  className="block text-sm font-medium text-slate-700 dark:text-slate-300"
                >
                  Sync Schedule
                </label>
                <select
                  id="sync-schedule"
                  value={syncHours}
                  onChange={(e) => setSyncHours(Number(e.target.value))}
                  className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:focus:border-brand-400 dark:focus:ring-brand-400"
                >
                  {SYNC_SCHEDULE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Baseline Window */}
              <div>
                <label
                  htmlFor="baseline-window"
                  className="block text-sm font-medium text-slate-700 dark:text-slate-300"
                >
                  Baseline Window
                </label>
                <select
                  id="baseline-window"
                  value={baselineDays}
                  onChange={(e) => setBaselineDays(Number(e.target.value))}
                  className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:focus:border-brand-400 dark:focus:ring-brand-400"
                >
                  {BASELINE_WINDOW_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </section>

          {/* Save button */}
          <button
            onClick={handleSave}
            disabled={!isDirty || updateMutation.isPending}
            className={clsx(
              "inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium text-white transition-colors",
              !isDirty || updateMutation.isPending
                ? "cursor-not-allowed bg-brand-400 dark:bg-brand-600"
                : "bg-brand-600 hover:bg-brand-700 dark:bg-brand-500 dark:hover:bg-brand-600",
            )}
          >
            {updateMutation.isPending ? (
              <>
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
                Saving...
              </>
            ) : (
              "Save Changes"
            )}
          </button>
        </div>
      ) : null}
    </div>
  );
}
