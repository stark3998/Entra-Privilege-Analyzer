import { useNavigate } from "react-router-dom";
import { useProjectContext } from "@/store/projectContext";
import type { PimSession } from "@/api/types";

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-300",
  expired: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
  deactivated: "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300",
};

export function PimSessionTable({ sessions }: { sessions: PimSession[] }) {
  const navigate = useNavigate();
  const { projectId } = useProjectContext();

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 dark:bg-slate-800">
          <tr>
            <th className="px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Identity</th>
            <th className="px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Role</th>
            <th className="px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Scope</th>
            <th className="px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Activated</th>
            <th className="px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Duration</th>
            <th className="px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Events</th>
            <th className="px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Anomalies</th>
            <th className="px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 bg-white dark:divide-slate-700 dark:bg-slate-900">
          {sessions.map((s) => (
            <tr
              key={s.id}
              onClick={() => navigate(`/projects/${projectId}/pim-sessions/${s.id}`)}
              className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              <td className="px-4 py-3">
                <div className="font-medium text-slate-900 dark:text-white">{s.principal_display_name}</div>
                {s.principal_upn && (
                  <div className="text-xs text-slate-500 dark:text-slate-400">{s.principal_upn}</div>
                )}
              </td>
              <td className="px-4 py-3 text-slate-700 dark:text-slate-300">{s.role_name}</td>
              <td className="px-4 py-3">
                <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                  s.session_scope === "entra_directory"
                    ? "bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300"
                    : "bg-purple-50 text-purple-700 dark:bg-purple-900/20 dark:text-purple-300"
                }`}>
                  {s.session_scope === "entra_directory" ? "Entra" : "Azure"}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                {new Date(s.activation_time).toLocaleString(undefined, {
                  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                })}
              </td>
              <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                {formatDuration(s.duration_minutes)}
              </td>
              <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                {s.total_event_count}
              </td>
              <td className="px-4 py-3">
                {s.anomalies.length > 0 ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/20 dark:text-red-300">
                    {s.anomalies.length}
                  </span>
                ) : (
                  <span className="text-slate-400 dark:text-slate-500">-</span>
                )}
              </td>
              <td className="px-4 py-3">
                <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[s.status] ?? STATUS_STYLES.expired}`}>
                  {s.is_active && <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />}
                  {s.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
