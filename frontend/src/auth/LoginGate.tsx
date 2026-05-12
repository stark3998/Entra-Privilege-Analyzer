// frontend/src/auth/LoginGate.tsx
import { useMsal } from "@azure/msal-react";
import { apiScopes } from "./msal";

export function LoginGate() {
  const { instance } = useMsal();

  function handleSignIn() {
    instance.loginRedirect({ scopes: apiScopes });
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 via-brand-50/30 to-slate-100 dark:from-slate-950 dark:via-brand-950/20 dark:to-slate-900">
      <div className="w-full max-w-md animate-fade-in space-y-8 rounded-2xl border border-slate-200/60 bg-white/80 p-10 shadow-card backdrop-blur-sm dark:border-slate-700/60 dark:bg-slate-900/80">
        <div className="text-center">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-600 shadow-lg shadow-brand-500/25">
            <svg
              className="h-8 w-8 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Entra Permissions Analyzer
          </h1>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            Least Privilege Analysis &amp; Role Advisory
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
    </div>
  );
}
