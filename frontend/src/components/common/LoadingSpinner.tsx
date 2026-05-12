interface LoadingSpinnerProps {
  size?: string;
  message?: string;
}

export function LoadingSpinner({ size = "h-8 w-8", message }: LoadingSpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center py-14">
      <div className="rounded-2xl bg-brand-50 p-4 dark:bg-brand-950/30">
        <svg
          className={`${size} animate-spin text-brand-600 dark:text-brand-400`}
          viewBox="0 0 24 24"
          fill="none"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      </div>
      {message && (
        <p className="mt-4 text-sm font-medium text-slate-500 dark:text-slate-400">
          {message}
        </p>
      )}
    </div>
  );
}
