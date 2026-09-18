import type { ActionEvent, PimSession } from "@/api/types";
import { MotionItem, MotionStagger } from "@/components/common/motion";

const RESULT_DOT: Record<string, string> = {
  success: "bg-green-500",
  failure: "bg-red-500",
};

export function SessionTimeline({
  events,
  session,
}: {
  events: ActionEvent[];
  session: PimSession;
}) {
  return (
    <div className="mt-4 space-y-0">
      {/* Activation marker */}
      <div className="flex items-start gap-3 pb-4">
        <div className="flex flex-col items-center">
          <div className="h-3 w-3 rounded-full bg-brand-500 ring-2 ring-brand-200 dark:ring-brand-800" />
          <div className="w-px flex-1 bg-slate-200 dark:bg-slate-700" />
        </div>
        <div className="-mt-0.5">
          <p className="text-sm font-semibold text-brand-700 dark:text-brand-300">
            Role Activated: {session.role_name}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {new Date(session.activation_time).toLocaleString()}
          </p>
        </div>
      </div>

      {/* Events */}
      <MotionStagger className="space-y-0">
      {events.map((evt, idx) => (
        <MotionItem key={evt.id} className="flex items-start gap-3 pb-4">
          <div className="flex flex-col items-center">
            <div className={`h-2 w-2 rounded-full ${RESULT_DOT[evt.result] ?? "bg-slate-400"}`} />
            {idx < events.length - 1 && (
              <div className="w-px flex-1 bg-slate-200 dark:bg-slate-700" />
            )}
          </div>
          <div className="-mt-0.5 flex-1">
            <div className="flex items-center justify-between">
              <p className="text-sm text-slate-900 dark:text-white">{evt.action}</p>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {new Date(evt.timestamp).toLocaleTimeString()}
              </span>
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
              {evt.resource && <span>{evt.resource}</span>}
              {evt.ip_address && <span className="font-mono">{evt.ip_address}</span>}
              {evt.result === "failure" && (
                <span className="text-red-600 dark:text-red-400">failed</span>
              )}
            </div>
          </div>
        </MotionItem>
      ))}
      </MotionStagger>

      {/* Expiry marker */}
      <div className="flex items-start gap-3">
        <div className="flex flex-col items-center">
          <div className={`h-3 w-3 rounded-full ring-2 ${
            session.is_active
              ? "bg-emerald-500 ring-emerald-200 dark:ring-emerald-800"
              : "bg-slate-400 ring-slate-200 dark:ring-slate-700"
          }`} />
        </div>
        <div className="-mt-0.5">
          <p className={`text-sm font-semibold ${
            session.is_active
              ? "text-emerald-700 dark:text-emerald-300"
              : "text-slate-600 dark:text-slate-400"
          }`}>
            {session.is_active ? "Session Active" : "Session Expired"}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {new Date(session.expiry_time).toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
}
