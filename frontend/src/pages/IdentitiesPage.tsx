// frontend/src/pages/IdentitiesPage.tsx
import { useState, useEffect, useCallback, useRef } from "react";
import { useIdentities } from "@/api/hooks";
import { IdentityTable } from "@/components/identities/IdentityTable";
import type { IdentityType } from "@/api/types";

const TYPE_OPTIONS: { label: string; value: IdentityType | "" }[] = [
  { label: "All Types", value: "" },
  { label: "User", value: "User" },
  { label: "Service Principal", value: "ServicePrincipal" },
  { label: "Managed Identity", value: "ManagedIdentity" },
  { label: "Group", value: "Group" },
];

const PAGE_SIZE = 50;

/** Debounce delay for the search input, in milliseconds. */
const DEBOUNCE_MS = 300;

export function IdentitiesPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<IdentityType | "">("");
  const [page, setPage] = useState(1);

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

  const { data, isLoading } = useIdentities({
    type: typeFilter || undefined,
    search: debouncedSearch || undefined,
    page,
    size: PAGE_SIZE,
  });

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          Identities
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Browse and inspect all Entra ID identities, their roles, and activity
        </p>
      </div>

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
            placeholder="Search by name, UPN, or app ID..."
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
      </div>

      {/* Table */}
      <IdentityTable
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
