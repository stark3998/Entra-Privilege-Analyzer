// frontend/src/components/layout/Header.tsx
import { useAuth } from "@/auth/useAuth";
import { useDarkMode } from "@/hooks/useDarkMode";

export function Header() {
  const { user, signOut } = useAuth();
  const [isDark, toggleDark] = useDarkMode();

  return (
    <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-brand-600 px-4 dark:border-slate-700 dark:bg-slate-800">
      {/* Left: App name */}
      <div className="flex items-center gap-2">
        <svg
          className="h-6 w-6 text-white"
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
        <span className="text-lg font-semibold text-white">
          Entra Analyzer
        </span>
      </div>

      {/* Right: Controls */}
      <div className="flex items-center gap-4">
        {/* Dark mode toggle */}
        <button
          onClick={toggleDark}
          className="rounded-md p-1.5 text-white/80 transition-colors hover:bg-white/10 hover:text-white"
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
        >
          {isDark ? (
            // Sun icon
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
              />
            </svg>
          ) : (
            // Moon icon
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
              />
            </svg>
          )}
        </button>

        {/* User name */}
        {user && (
          <span className="hidden text-sm font-medium text-white/90 sm:inline">
            {user.name}
          </span>
        )}

        {/* Sign out */}
        <button
          onClick={() => void signOut()}
          className="rounded-md px-3 py-1.5 text-sm font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
