import type { PimSessionAnomaly } from "@/api/types";

const SEVERITY_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  critical: { bg: "bg-red-50 dark:bg-red-900/20", text: "text-red-700 dark:text-red-300", dot: "bg-red-500" },
  high: { bg: "bg-orange-50 dark:bg-orange-900/20", text: "text-orange-700 dark:text-orange-300", dot: "bg-orange-500" },
  medium: { bg: "bg-amber-50 dark:bg-amber-900/20", text: "text-amber-700 dark:text-amber-300", dot: "bg-amber-500" },
  low: { bg: "bg-slate-50 dark:bg-slate-800", text: "text-slate-700 dark:text-slate-300", dot: "bg-slate-400" },
};

const ANOMALY_LABELS: Record<string, string> = {
  unusual_activation_time: "Unusual Activation Time",
  new_location: "New Location",
  first_time_role: "First-Time Role Activation",
  high_volume_actions: "High Volume Actions",
  sensitive_action: "Sensitive Action Detected",
  no_justification: "Missing Justification",
};

export function AnomalyList({ anomalies }: { anomalies: PimSessionAnomaly[] }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
      <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
        Anomalies ({anomalies.length})
      </h2>
      <div className="mt-3 space-y-2">
        {anomalies.map((a, i) => {
          const s = SEVERITY_STYLES[a.severity] ?? SEVERITY_STYLES.medium;
          return (
            <div key={i} className={`flex items-start gap-3 rounded-lg px-4 py-3 ${s.bg}`}>
              <span className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${s.dot}`} />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-medium ${s.text}`}>
                    {ANOMALY_LABELS[a.anomaly_type] ?? a.anomaly_type}
                  </span>
                  <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold uppercase ${s.text}`}>
                    {a.severity}
                  </span>
                </div>
                <p className={`mt-0.5 text-xs ${s.text} opacity-80`}>{a.details}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
