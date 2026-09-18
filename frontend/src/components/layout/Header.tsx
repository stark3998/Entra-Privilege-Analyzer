import { useAuth } from "@/auth/useAuth";
import { useDarkMode } from "@/hooks/useDarkMode";
import { Tooltip } from "@/components/common/Tooltip";
import { LogoBadge } from "@/components/common/Logo";
import { useProjectContext } from "@/store/projectContext";
import { useCommandPalette } from "./CommandPalette";

export function Header() {
  const { user, signOut } = useAuth();
  const [isDark, toggleDark] = useDarkMode();
  const { project } = useProjectContext();
  const { open: openCommandPalette } = useCommandPalette();

  const initials = user?.name
    ? user.name
        .split(" ")
        .map((w) => w[0])
        .join("")
        .slice(0, 2)
        .toUpperCase()
    : "?";

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-200/80 bg-white px-6 dark:border-slate-700/80 dark:bg-slate-900">
      {/* Left: Logo + App name */}
      <div className="flex items-center gap-3">
        <LogoBadge size="md" />
        <div>
          <div className="flex items-center gap-1.5">
            <h1 className="text-base font-bold tracking-tight text-slate-900 dark:text-white">
              Entra Analyzer
            </h1>
            {project && (
              <>
                <svg className="h-3.5 w-3.5 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
                <span className="text-sm font-medium text-slate-600 dark:text-slate-400">
                  {project.name}
                </span>
              </>
            )}
          </div>
          <p className="text-[11px] font-medium text-slate-400 dark:text-slate-500">
            Least Privilege Advisory
          </p>
        </div>
      </div>

      {/* Center: Global search trigger */}
      <div className="flex flex-1 justify-center px-6">
        <button
          onClick={openCommandPalette}
          className="group flex w-full max-w-md items-center gap-2.5 rounded-xl border border-slate-200 bg-slate-50/80 px-3.5 py-2 text-sm text-slate-400 shadow-xs transition-all hover:border-brand-300 hover:bg-white hover:text-slate-500 dark:border-slate-700 dark:bg-slate-800/60 dark:hover:border-brand-700 dark:hover:bg-slate-800"
          aria-label="Open command palette"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <span className="flex-1 text-left">Search or jump to…</span>
          <kbd className="hidden items-center gap-0.5 rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-slate-400 shadow-xs group-hover:border-brand-200 dark:border-slate-600 dark:bg-slate-900 sm:flex">
            <span className="text-xs">⌘</span>K
          </kbd>
        </button>
      </div>

      {/* Right: Controls */}
      <div className="flex items-center gap-2">
        {/* Dark mode toggle */}
        <Tooltip content={isDark ? "Switch to light mode" : "Switch to dark mode"}>
          <button
            onClick={toggleDark}
            className="flex h-9 w-9 items-center justify-center rounded-xl text-slate-500 transition-all hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
          >
            {isDark ? (
              <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            ) : (
              <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>
        </Tooltip>

        {/* Divider */}
        <div className="mx-1 h-6 w-px bg-slate-200 dark:bg-slate-700" />

        {/* User avatar + name */}
        {user && (
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700 dark:bg-brand-900/40 dark:text-brand-300">
              {initials}
            </div>
            <span className="hidden text-sm font-medium text-slate-700 dark:text-slate-300 sm:inline">
              {user.name}
            </span>
          </div>
        )}

        {/* Sign out */}
        <Tooltip content="Sign out">
          <button
            onClick={() => void signOut()}
            className="flex h-9 w-9 items-center justify-center rounded-xl text-slate-400 transition-all hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20 dark:hover:text-red-400"
            aria-label="Sign out"
          >
            <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </Tooltip>
      </div>
    </header>
  );
}
