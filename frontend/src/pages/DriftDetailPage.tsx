// frontend/src/pages/DriftDetailPage.tsx
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import clsx from "clsx";
import { useDriftAlertDetail, useUpdateDriftAlert } from "@/api/hooks";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EmptyState } from "@/components/common/EmptyState";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { DriftTimeline } from "@/components/drift/DriftTimeline";
import { AcknowledgeDialog } from "@/components/drift/AcknowledgeDialog";
import { ApiError } from "@/api/client";
import { formatRelativeTime } from "@/utils/formatRelativeTime";
import type { DriftStatus, DriftType } from "@/api/types";

const DRIFT_TYPE_COLORS: Record<DriftType, string> = {
  first_seen: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  frequency_anomaly: "bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
};

const DRIFT_TYPE_LABELS: Record<DriftType, string> = {
  first_seen: "First Seen",
  frequency_anomaly: "Frequency Anomaly",
};

const STATUS_COLORS: Record<DriftStatus, string> = {
  open: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  acknowledged: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  escalated: "bg-orange-50 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  resolved: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
};

/** Z-score visual gauge as a horizontal bar. */
function ZScoreGauge({
  zScore,
  mean,
  stddev,
}: {
  zScore: number;
  mean: number;
  stddev: number;
}) {
  // Clamp display to 0-10 range for the gauge
  const clampedScore = Math.min(Math.max(zScore, 0), 10);
  const percentage = (clampedScore / 10) * 100;

  const barColor =
    zScore >= 4
      ? "bg-red-500"
      : zScore >= 3
        ? "bg-orange-500"
        : zScore >= 2
          ? "bg-amber-500"
          : "bg-emerald-500";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-slate-700 dark:text-slate-300">
          Z-Score
        </span>
        <span className="tabular-nums font-bold text-slate-900 dark:text-white">
          {zScore.toFixed(2)}
        </span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div
          className={clsx("h-full rounded-full transition-all", barColor)}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Baseline Mean
          </p>
          <p className="text-sm font-semibold tabular-nums text-slate-900 dark:text-white">
            {mean.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Std Deviation
          </p>
          <p className="text-sm font-semibold tabular-nums text-slate-900 dark:text-white">
            {stddev.toFixed(2)}
          </p>
        </div>
      </div>
    </div>
  );
}

export function DriftDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, isLoading, isError, error } = useDriftAlertDetail(id ?? "");
  const updateMutation = useUpdateDriftAlert();

  const [dialogStatus, setDialogStatus] = useState<DriftStatus | null>(null);

  const handleStatusUpdate = (notes: string) => {
    if (!data || !dialogStatus) return;
    updateMutation.mutate(
      { alertId: data.id, status: dialogStatus, notes },
      { onSuccess: () => setDialogStatus(null) },
    );
  };

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={() => navigate("/drift")}
        className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-sm font-medium text-slate-600 transition-colors hover:bg-brand-50 hover:text-brand-700 dark:text-slate-400 dark:hover:bg-brand-900/20 dark:hover:text-brand-300"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Back to Drift Monitor
      </button>

      {/* Loading */}
      {isLoading && (
        <LoadingSpinner message="Loading drift alert details..." />
      )}

      {/* Error / 404 */}
      {isError && (
        <EmptyState
          title={
            error instanceof ApiError && error.status === 404
              ? "Drift alert not found"
              : "Failed to load drift alert"
          }
          description={
            error instanceof ApiError && error.status === 404
              ? "This drift alert does not exist or has been removed."
              : error instanceof Error
                ? error.message
                : "An unexpected error occurred."
          }
          icon={
            <svg
              className="h-10 w-10"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          }
          action={
            <button type="button" onClick={() => navigate("/drift")} className="btn-primary">
              Return to Drift Monitor
            </button>
          }
        />
      )}

      {/* Detail view */}
      {data && (
        <div className="space-y-8">
          {/* Header */}
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge severity={data.severity} size="md" />
                <span
                  className={clsx(
                    "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium",
                    DRIFT_TYPE_COLORS[data.drift_type],
                  )}
                >
                  {DRIFT_TYPE_LABELS[data.drift_type]}
                </span>
                <span
                  className={clsx(
                    "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                    STATUS_COLORS[data.status],
                  )}
                >
                  {data.status}
                </span>
              </div>
              <h1 className="page-title mt-2">{data.identity_display_name}</h1>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Detected {formatRelativeTime(data.detected_at)}
              </p>
            </div>

            {/* Status action buttons */}
            <div className="flex flex-wrap gap-2">
              {data.status === "open" && (
                <>
                  <button
                    onClick={() => setDialogStatus("acknowledged")}
                    className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-700 transition-colors hover:bg-amber-100 dark:border-amber-700 dark:bg-amber-900/20 dark:text-amber-300 dark:hover:bg-amber-900/40"
                  >
                    Acknowledge
                  </button>
                  <button
                    onClick={() => setDialogStatus("escalated")}
                    className="rounded-lg border border-orange-300 bg-orange-50 px-3 py-1.5 text-sm font-medium text-orange-700 transition-colors hover:bg-orange-100 dark:border-orange-700 dark:bg-orange-900/20 dark:text-orange-300 dark:hover:bg-orange-900/40"
                  >
                    Escalate
                  </button>
                </>
              )}
              {data.status === "acknowledged" && (
                <>
                  <button
                    onClick={() => setDialogStatus("escalated")}
                    className="rounded-lg border border-orange-300 bg-orange-50 px-3 py-1.5 text-sm font-medium text-orange-700 transition-colors hover:bg-orange-100 dark:border-orange-700 dark:bg-orange-900/20 dark:text-orange-300 dark:hover:bg-orange-900/40"
                  >
                    Escalate
                  </button>
                  <button
                    onClick={() => setDialogStatus("resolved")}
                    className="rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-100 dark:border-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300 dark:hover:bg-emerald-900/40"
                  >
                    Resolve
                  </button>
                </>
              )}
              {data.status === "escalated" && (
                <button
                  onClick={() => setDialogStatus("resolved")}
                  className="rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-100 dark:border-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300 dark:hover:bg-emerald-900/40"
                >
                  Resolve
                </button>
              )}
            </div>
          </div>

          {/* Mutation feedback */}
          {updateMutation.isError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
              Failed to update alert:{" "}
              {updateMutation.error instanceof Error
                ? updateMutation.error.message
                : "Unknown error"}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="card px-4 py-3">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Action</p>
              <p className="mt-1 truncate text-sm font-bold text-slate-900 dark:text-white" title={data.action}>{data.action}</p>
            </div>
            <div className="card px-4 py-3">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Resource</p>
              <p className="mt-1 truncate text-sm font-bold text-slate-900 dark:text-white" title={data.resource ?? undefined}>
                {data.resource ?? <span className="text-slate-400 dark:text-slate-500">--</span>}
              </p>
            </div>
            <div className="card px-4 py-3">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Observed Count</p>
              <p className="mt-1 text-xl font-bold tabular-nums text-slate-900 dark:text-white">{data.observed_count ?? "--"}</p>
            </div>
            <div className="card px-4 py-3">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Detected At</p>
              <p className="mt-1 text-sm font-bold text-slate-900 dark:text-white">{formatRelativeTime(data.detected_at)}</p>
            </div>
          </div>

          <section>
            <h2 className="section-title mb-3">Details</h2>
            <div className="card p-5">
              <p className="text-sm text-slate-700 dark:text-slate-300">
                {data.details}
              </p>
            </div>
          </section>

          {/* Frequency anomaly stats */}
          {data.drift_type === "frequency_anomaly" &&
            data.z_score != null &&
            data.baseline_mean != null &&
            data.baseline_stddev != null && (
              <section>
                <h2 className="section-title mb-3">Frequency Analysis</h2>
                <div className="card p-5">
                  <ZScoreGauge
                    zScore={data.z_score}
                    mean={data.baseline_mean}
                    stddev={data.baseline_stddev}
                  />
                </div>
              </section>
            )}

          {data.acknowledged_by && (
            <section>
              <h2 className="section-title mb-3">Acknowledgment</h2>
              <div className="card p-5">
                <p className="text-sm text-slate-700 dark:text-slate-300">
                  Acknowledged by{" "}
                  <span className="font-medium">{data.acknowledged_by}</span>
                  {data.acknowledged_at && (
                    <span>
                      {" "}
                      on {formatRelativeTime(data.acknowledged_at)}
                    </span>
                  )}
                </p>
              </div>
            </section>
          )}

          <section>
            <h2 className="section-title mb-3">Action Timeline</h2>
            <DriftTimeline
              identityId={data.identity_id}
              highlightAction={data.action}
              baselineMean={data.baseline_mean}
            />
          </section>
        </div>
      )}

      {/* Confirmation dialog */}
      {dialogStatus && data && (
        <AcknowledgeDialog
          alert={data}
          targetStatus={dialogStatus}
          onConfirm={handleStatusUpdate}
          onCancel={() => setDialogStatus(null)}
          isPending={updateMutation.isPending}
        />
      )}
    </div>
  );
}
