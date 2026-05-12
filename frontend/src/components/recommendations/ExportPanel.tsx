// frontend/src/components/recommendations/ExportPanel.tsx
import { useState, useCallback } from "react";
import clsx from "clsx";
import { useExport } from "@/api/hooks";
import type { ExportFormat } from "@/api/types";
import { JsonViewer } from "@/components/common/JsonViewer";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";

interface ExportPanelProps {
  identityId: string;
}

interface FormatOption {
  key: ExportFormat;
  label: string;
  language: string;
  color: string;
  activeColor: string;
}

const FORMAT_OPTIONS: FormatOption[] = [
  {
    key: "terraform",
    label: "Terraform",
    language: "hcl",
    color:
      "border-purple-300 text-purple-700 hover:bg-purple-50 dark:border-purple-700 dark:text-purple-400 dark:hover:bg-purple-900/20",
    activeColor:
      "border-purple-500 bg-purple-50 text-purple-700 dark:border-purple-500 dark:bg-purple-900/30 dark:text-purple-300",
  },
  {
    key: "bicep",
    label: "Bicep",
    language: "bicep",
    color:
      "border-sky-300 text-sky-700 hover:bg-sky-50 dark:border-sky-700 dark:text-sky-400 dark:hover:bg-sky-900/20",
    activeColor:
      "border-sky-500 bg-sky-50 text-sky-700 dark:border-sky-500 dark:bg-sky-900/30 dark:text-sky-300",
  },
  {
    key: "arm",
    label: "ARM JSON",
    language: "json",
    color:
      "border-orange-300 text-orange-700 hover:bg-orange-50 dark:border-orange-700 dark:text-orange-400 dark:hover:bg-orange-900/20",
    activeColor:
      "border-orange-500 bg-orange-50 text-orange-700 dark:border-orange-500 dark:bg-orange-900/30 dark:text-orange-300",
  },
];

/**
 * IaC export panel with Terraform, Bicep, and ARM JSON buttons.
 * Fetches export content on demand and provides download + copy functionality.
 *
 * Usage:
 * ```tsx
 * <ExportPanel identityId={rec.identity_id} />
 * ```
 */
export function ExportPanel({ identityId }: ExportPanelProps) {
  const [activeFormat, setActiveFormat] = useState<ExportFormat | null>(null);

  const terraformQuery = useExport(identityId, "terraform");
  const bicepQuery = useExport(identityId, "bicep");
  const armQuery = useExport(identityId, "arm");

  const queryMap: Record<ExportFormat, typeof terraformQuery> = {
    terraform: terraformQuery,
    bicep: bicepQuery,
    arm: armQuery,
  };

  const handleFormatClick = useCallback(
    (format: ExportFormat) => {
      setActiveFormat(format);
      const query = queryMap[format];
      // Only refetch if we haven't loaded data yet
      if (!query.data) {
        query.refetch();
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [terraformQuery.data, bicepQuery.data, armQuery.data],
  );

  const handleDownload = useCallback(() => {
    if (!activeFormat) return;
    const query = queryMap[activeFormat];
    if (!query.data) return;

    const blob = new Blob([query.data.content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = query.data.filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFormat, terraformQuery.data, bicepQuery.data, armQuery.data]);

  const activeQuery = activeFormat ? queryMap[activeFormat] : null;
  const activeOption = FORMAT_OPTIONS.find((o) => o.key === activeFormat);

  return (
    <div className="space-y-4">
      {/* Format buttons */}
      <div className="flex flex-wrap gap-2">
        {FORMAT_OPTIONS.map((opt) => (
          <button
            key={opt.key}
            onClick={() => handleFormatClick(opt.key)}
            className={clsx(
              "rounded-lg border px-4 py-2 text-sm font-medium transition-colors",
              activeFormat === opt.key ? opt.activeColor : opt.color,
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Content area */}
      {activeFormat && activeQuery && (
        <div className="space-y-3">
          {activeQuery.isFetching && (
            <LoadingSpinner message={`Generating ${activeFormat} export...`} />
          )}

          {activeQuery.isError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
              Failed to generate export:{" "}
              {activeQuery.error instanceof Error
                ? activeQuery.error.message
                : "Unknown error"}
            </div>
          )}

          {activeQuery.data && (
            <>
              {/* Action buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={handleDownload}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
                >
                  <svg
                    className="h-3.5 w-3.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                    />
                  </svg>
                  Download {activeQuery.data.filename}
                </button>
              </div>

              {/* Code viewer */}
              <JsonViewer
                content={activeQuery.data.content}
                language={activeOption?.language}
                maxHeight="max-h-96"
              />
            </>
          )}
        </div>
      )}

      {!activeFormat && (
        <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">
          Select a format above to generate an IaC export
        </p>
      )}
    </div>
  );
}
