// frontend/src/pages/ReportsPage.tsx
import { useCallback } from "react";
import clsx from "clsx";
import { useDownloadReport } from "@/api/hooks";

interface ReportCardProps {
  title: string;
  description: string;
  format: "pdf" | "pptx";
  icon: React.ReactNode;
}

function ReportCard({ title, description, format, icon }: ReportCardProps) {
  const { isFetching, refetch } = useDownloadReport(format);

  const handleDownload = useCallback(async () => {
    const result = await refetch();
    if (result.data) {
      const blob = result.data;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `executive-report.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  }, [refetch, format]);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-start gap-4">
        <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-lg bg-brand-100 text-brand-600 dark:bg-brand-900/30 dark:text-brand-400">
          {icon}
        </div>
        <div className="flex-1">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">
            {title}
          </h3>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {description}
          </p>
          <button
            onClick={handleDownload}
            disabled={isFetching}
            className={clsx(
              "mt-4 inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors",
              isFetching
                ? "cursor-not-allowed bg-brand-400 dark:bg-brand-600"
                : "bg-brand-600 hover:bg-brand-700 dark:bg-brand-500 dark:hover:bg-brand-600",
            )}
          >
            {isFetching ? (
              <>
                <svg
                  className="h-4 w-4 animate-spin"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Downloading...
              </>
            ) : (
              <>
                <svg
                  className="h-4 w-4"
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
                Download
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export function ReportsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          Reports
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Download executive reports summarizing your Entra ID permissions posture
        </p>
      </div>

      {/* Report cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ReportCard
          title="Executive PDF Report"
          description="A comprehensive PDF report with risk scores, compliance status, drift analysis, and AI-generated executive narrative. Ideal for sharing with leadership."
          format="pdf"
          icon={
            <svg
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
              />
            </svg>
          }
        />
        <ReportCard
          title="Executive PowerPoint Report"
          description="A presentation-ready slide deck with key metrics, trend visualizations, and actionable recommendations. Perfect for board meetings."
          format="pptx"
          icon={
            <svg
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5"
              />
            </svg>
          }
        />
      </div>
    </div>
  );
}
