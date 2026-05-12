// frontend/src/pages/RecommendationsPage.tsx
import { useState, useEffect, useCallback, useRef } from "react";
import clsx from "clsx";
import { useRecommendations, useComputeRecommendations } from "@/api/hooks";
import { useAuth } from "@/auth/useAuth";
import { RecommendationList } from "@/components/recommendations/RecommendationList";
import type { IdentityType } from "@/api/types";

const TYPE_OPTIONS: { label: string; value: IdentityType | "" }[] = [
  { label: "All Types", value: "" },
  { label: "User", value: "User" },
  { label: "Service Principal", value: "ServicePrincipal" },
  { label: "Managed Identity", value: "ManagedIdentity" },
  { label: "Group", value: "Group" },
];

const SORT_OPTIONS: { label: string; value: string }[] = [
  { label: "Highest Reduction First", value: "reduction_desc" },
  { label: "Most Permissions Removed", value: "excess_desc" },
  { label: "By Name", value: "name_asc" },
];

const PAGE_SIZE = 20;

/** Debounce delay for the search input, in milliseconds. */
const DEBOUNCE_MS = 300;

export function RecommendationsPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<IdentityType | "">("");
  const [sort, setSort] = useState("reduction_desc");
  const [page, setPage] = useState(1);

  const { roles } = useAuth();
  const isIAMAdmin = roles.includes("IAMAdmin");

  // Debounce search input
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setDebouncedSearch(value);
      setPage(1);
    }, DEBOUNCE_MS);
  }, []);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  // Reset to page 1 when filter changes
  const handleTypeChange = useCallback((value: string) => {
    setTypeFilter(value as IdentityType | "");
    setPage(1);
  }, []);

  const handleSortChange = useCallback((value: string) => {
    setSort(value);
    setPage(1);
  }, []);

  const { data, isLoading } = useRecommendations({
    type: typeFilter || undefined,
    search: debouncedSearch || undefined,
    sort,
    page,
    size: PAGE_SIZE,
  });

  const computeMutation = useComputeRecommendations();

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Role Recommendations
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Least-privilege role recommendations based on observed permission
            usage
          </p>
        </div>

        {/* Compute button — only for IAMAdmin */}
        {isIAMAdmin && (
          <button
            onClick={() => computeMutation.mutate()}
            disabled={computeMutation.isPending}
            className={clsx(
              "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors",
              computeMutation.isPending
                ? "cursor-not-allowed bg-brand-400 dark:bg-brand-600"
                : "bg-brand-600 hover:bg-brand-700 dark:bg-brand-500 dark:hover:bg-brand-600",
            )}
          >
            {computeMutation.isPending ? (
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
                Computing...
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
                    d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                  />
                </svg>
                Compute Recommendations
              </>
            )}
          </button>
        )}
      </div>

      {/* Success/Error banner for compute */}
      {computeMutation.isSuccess && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400">
          Recommendations computed successfully. Results are now loading.
        </div>
      )}
      {computeMutation.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          Failed to compute recommendations:{" "}
          {computeMutation.error instanceof Error
            ? computeMutation.error.message
            : "Unknown error"}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        {/* Search */}
        <div className="relative flex-1">
          <svg
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 dark:text-slate-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            placeholder="Search by identity name..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-10 pr-4 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500 dark:focus:border-brand-400 dark:focus:ring-brand-400"
          />
        </div>

        {/* Type filter */}
        <select
          value={typeFilter}
          onChange={(e) => handleTypeChange(e.target.value)}
          aria-label="Filter by identity type"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:focus:border-brand-400 dark:focus:ring-brand-400"
        >
          {TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Sort */}
        <select
          value={sort}
          onChange={(e) => handleSortChange(e.target.value)}
          aria-label="Sort recommendations"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:focus:border-brand-400 dark:focus:ring-brand-400"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Recommendation cards */}
      <RecommendationList
        data={data?.items ?? []}
        total={data?.total ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        isLoading={isLoading}
      />
    </div>
  );
}
