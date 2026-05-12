// frontend/src/components/best-practices/RemediationSteps.tsx
import { useState, useCallback } from "react";
import clsx from "clsx";

interface RemediationStepsProps {
  steps: string[];
}

/**
 * Numbered remediation step list with visual-only checkboxes (client-side toggle).
 * Styled with alternating backgrounds for readability.
 */
export function RemediationSteps({ steps }: RemediationStepsProps) {
  const [checked, setChecked] = useState<Record<number, boolean>>({});

  const toggle = useCallback((index: number) => {
    setChecked((prev) => ({ ...prev, [index]: !prev[index] }));
  }, []);

  if (steps.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-slate-400 dark:text-slate-500">
        No remediation steps available.
      </p>
    );
  }

  return (
    <ol className="divide-y divide-slate-200 dark:divide-slate-700">
      {steps.map((step, index) => (
        <li
          key={index}
          className={clsx(
            "flex items-start gap-3 px-4 py-3",
            index % 2 === 0
              ? "bg-white dark:bg-slate-900"
              : "bg-slate-50 dark:bg-slate-800/50",
          )}
        >
          {/* Checkbox */}
          <button
            onClick={() => toggle(index)}
            className={clsx(
              "mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded border transition-colors",
              checked[index]
                ? "border-emerald-500 bg-emerald-500 text-white dark:border-emerald-400 dark:bg-emerald-500"
                : "border-slate-300 bg-white dark:border-slate-600 dark:bg-slate-800",
            )}
            aria-label={`Mark step ${index + 1} as ${checked[index] ? "incomplete" : "complete"}`}
          >
            {checked[index] && (
              <svg
                className="h-3.5 w-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={3}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M5 13l4 4L19 7"
                />
              </svg>
            )}
          </button>

          {/* Step content */}
          <div className="min-w-0 flex-1">
            <span
              className={clsx(
                "mr-2 inline-flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold",
                "bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300",
              )}
            >
              {index + 1}
            </span>
            <span
              className={clsx(
                "text-sm",
                checked[index]
                  ? "text-slate-400 line-through dark:text-slate-500"
                  : "text-slate-700 dark:text-slate-300",
              )}
            >
              {step}
            </span>
          </div>
        </li>
      ))}
    </ol>
  );
}
