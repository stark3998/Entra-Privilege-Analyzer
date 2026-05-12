import { useState, useEffect, useCallback } from "react";
import clsx from "clsx";
import { useTenantSettings, useUpdateTenantSettings } from "@/api/hooks";
import { Tooltip } from "@/components/common/Tooltip";

const SYNC_SCHEDULE_OPTIONS: { label: string; value: number; hint: string }[] = [
  { label: "Every 1 hour", value: 1, hint: "Most frequent — higher API usage" },
  { label: "Every 3 hours", value: 3, hint: "Good balance of freshness and cost" },
  { label: "Every 6 hours", value: 6, hint: "Default — recommended for most tenants" },
  { label: "Every 12 hours", value: 12, hint: "Reduced API calls" },
  { label: "Every 24 hours", value: 24, hint: "Minimum frequency" },
];

const BASELINE_WINDOW_OPTIONS: { label: string; value: number; hint: string }[] = [
  { label: "7 days", value: 7, hint: "Short window — more sensitive to drift" },
  { label: "14 days", value: 14, hint: "Two-week rolling baseline" },
  { label: "30 days", value: 30, hint: "Default — recommended for stable environments" },
  { label: "60 days", value: 60, hint: "Extended window — reduces false positives" },
];

export function SettingsPage() {
  const { data: settings, isLoading, isError } = useTenantSettings();
  const updateMutation = useUpdateTenantSettings();

  const [syncHours, setSyncHours] = useState<number>(6);
  const [baselineDays, setBaselineDays] = useState<number>(30);
  const [showToast, setShowToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    if (settings) {
      setSyncHours(settings.sync_schedule_hours);
      setBaselineDays(settings.baseline_window_days);
    }
  }, [settings]);

  useEffect(() => {
    if (!showToast) return;
    const timer = setTimeout(() => setShowToast(null), 4000);
    return () => clearTimeout(timer);
  }, [showToast]);

  const isDirty =
    settings !== undefined &&
    (syncHours !== settings.sync_schedule_hours || baselineDays !== settings.baseline_window_days);

  const handleSave = useCallback(() => {
    updateMutation.mutate(
      { sync_schedule_hours: syncHours, baseline_window_days: baselineDays },
      {
        onSuccess: () => setShowToast({ type: "success", message: "Settings saved successfully." }),
        onError: (err) => setShowToast({ type: "error", message: err instanceof Error ? err.message : "Failed to save settings." }),
      },
    );
  }, [updateMutation, syncHours, baselineDays]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Configure tenant-level sync and baseline settings</p>
      </div>

      {showToast && (
        <div
          className={clsx(
            "card animate-slide-up p-3 text-sm font-medium",
            showToast.type === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400"
              : "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400",
          )}
        >
          {showToast.message}
        </div>
      )}

      {isError && (
        <div className="card border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          Failed to load settings. Please try again later.
        </div>
      )}

      {isLoading ? (
        <div className="animate-pulse space-y-4">
          <div className="h-10 w-2/3 rounded-xl bg-slate-100 dark:bg-slate-800" />
          <div className="h-10 w-2/3 rounded-xl bg-slate-100 dark:bg-slate-800" />
        </div>
      ) : settings ? (
        <div className="max-w-xl space-y-8">
          <section className="card p-6">
            <div className="flex items-center gap-2">
              <h2 className="section-title">Sync Configuration</h2>
              <Tooltip content="Controls how often data is fetched from Microsoft Graph API">
                <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </Tooltip>
            </div>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Control how frequently data is synced from Entra ID.
            </p>

            <div className="mt-5 space-y-5">
              <div>
                <label htmlFor="sync-schedule" className="block text-sm font-semibold text-slate-700 dark:text-slate-300">
                  Sync Schedule
                </label>
                <select id="sync-schedule" value={syncHours} onChange={(e) => setSyncHours(Number(e.target.value))} className="input-base mt-1.5 block w-full">
                  {SYNC_SCHEDULE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
                <p className="mt-1.5 text-xs text-slate-400 dark:text-slate-500">
                  {SYNC_SCHEDULE_OPTIONS.find((o) => o.value === syncHours)?.hint}
                </p>
              </div>

              <div>
                <label htmlFor="baseline-window" className="block text-sm font-semibold text-slate-700 dark:text-slate-300">
                  Baseline Window
                </label>
                <select id="baseline-window" value={baselineDays} onChange={(e) => setBaselineDays(Number(e.target.value))} className="input-base mt-1.5 block w-full">
                  {BASELINE_WINDOW_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
                <p className="mt-1.5 text-xs text-slate-400 dark:text-slate-500">
                  {BASELINE_WINDOW_OPTIONS.find((o) => o.value === baselineDays)?.hint}
                </p>
              </div>
            </div>
          </section>

          <button
            type="button"
            onClick={handleSave}
            disabled={!isDirty || updateMutation.isPending}
            className="btn-primary"
          >
            {updateMutation.isPending ? (
              <>
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
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
