// frontend/src/auth/LoginGate.tsx
import { useMsal } from "@azure/msal-react";
import { MotionItem, MotionStagger } from "@/components/common/motion";
import { LogoBadge } from "@/components/common/Logo";
import { apiScopes } from "./msal";

export function LoginGate() {
  const { instance } = useMsal();

  function handleSignIn() {
    instance.loginRedirect({ scopes: apiScopes });
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-50 px-6 py-12 dark:bg-slate-950">
      <div className="absolute left-1/2 top-[-10rem] h-80 w-80 -translate-x-1/2 rounded-full bg-brand-500/15 blur-3xl dark:bg-brand-500/10" />
      <div className="absolute bottom-[-12rem] right-[-8rem] h-96 w-96 rounded-full bg-brand-400/10 blur-3xl dark:bg-brand-400/5" />

      <MotionStagger className="relative grid w-full max-w-5xl items-center gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <MotionItem>
          <div className="space-y-6">
            <span className="badge bg-brand-50 text-brand-700 ring-1 ring-brand-200/70 dark:bg-brand-900/20 dark:text-brand-300 dark:ring-brand-900/50">
              2027 SaaS security intelligence
            </span>
            <div>
              <p className="eyebrow">Entra Privilege Analyzer</p>
              <h1 className="mt-3 text-4xl font-bold tracking-[-0.04em] text-slate-950 dark:text-white sm:text-5xl">
                Make least privilege measurable.
              </h1>
              <p className="mt-4 max-w-xl text-base leading-7 text-slate-600 dark:text-slate-300">
                Connect Microsoft Entra ID, surface overprivilege, and brief leaders with confident, evidence-backed access posture.
              </p>
            </div>
            <div className="grid max-w-lg grid-cols-3 gap-3">
              {["Graph-aware", "AI narrative", "Audit ready"].map((label) => (
                <div key={label} className="card-glass px-3 py-2 text-center text-xs font-semibold text-slate-600 dark:text-slate-300">
                  {label}
                </div>
              ))}
            </div>
          </div>
        </MotionItem>

        <MotionItem>
        <div className="card-glass relative w-full overflow-hidden p-8 shadow-elevated">
          <div className="absolute inset-x-0 top-0 h-1 bg-brand-gradient" />
          <div className="text-center">
          <LogoBadge size="lg" className="mx-auto mb-5" />
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Entra Permissions Analyzer
          </h1>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            Least privilege analysis &amp; role advisory
          </p>
        </div>
        <button
          onClick={handleSignIn}
          className="btn-primary w-full justify-center gap-3 py-3"
        >
          <svg className="h-5 w-5" viewBox="0 0 21 21" fill="none">
            <rect x="1" y="1" width="9" height="9" fill="#f25022" />
            <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
            <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
            <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
          </svg>
          Sign in with Microsoft
        </button>
        <p className="text-center text-xs text-slate-400 dark:text-slate-500">
          Powered by Microsoft Entra ID
        </p>
      </div>
        </MotionItem>
      </MotionStagger>
    </div>
  );
}
