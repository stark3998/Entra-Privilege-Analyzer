import { useState, useEffect, useCallback, useRef } from "react";
import clsx from "clsx";
import { useIdentities } from "@/api/hooks";
import { IdentityTable } from "@/components/identities/IdentityTable";
import { Tooltip } from "@/components/common/Tooltip";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { MotionStagger, MotionItem } from "@/components/common/motion";
import { useProjectContext } from "@/store/projectContext";
import type { IdentityType } from "@/api/types";

const TYPE_OPTIONS: { label: string; value: IdentityType | "" }[] = [
  { label: "All Types", value: "" },
  { label: "User", value: "User" },
  { label: "Service Principal", value: "ServicePrincipal" },
  { label: "Managed Identity", value: "ManagedIdentity" },
  { label: "Group", value: "Group" },
];

const PAGE_SIZE = 50;
const DEBOUNCE_MS = 300;

const TYPE_FILTER_STYLES: Record<IdentityType, string> = {
  User: "bg-brand-50 text-brand-700 ring-brand-200 dark:bg-brand-950/40 dark:text-brand-300 dark:ring-brand-900/60",
  ServicePrincipal: "bg-violet-50 text-violet-700 ring-violet-200 dark:bg-violet-950/40 dark:text-violet-300 dark:ring-violet-900/60",
  ManagedIdentity: "bg-teal-50 text-teal-700 ring-teal-200 dark:bg-teal-950/40 dark:text-teal-300 dark:ring-teal-900/60",
  Group: "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900/60",
};

export function IdentitiesPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<IdentityType | "">("");
  const [page, setPage] = useState(1);
  const { project } = useProjectContext();

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setDebouncedSearch(value);
      setPage(1);
    }, DEBOUNCE_MS);
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

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

  const total = data?.total ?? 0;
  const hasFilters = Boolean(search || typeFilter);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Identity Inventory</p>
          <h1 className="page-title mt-1">Identities</h1>
          <p className="page-subtitle">
            Browse roles, activity, and risk signals for{" "}
            <span className="font-medium text-slate-600 dark:text-slate-300">
              {project?.target_tenant_name ?? "your tenant"}
            </span>
          </p>
        </div>

        <div className="card px-4 py-3">
          <p className="eyebrow">Total identities</p>
          <AnimatedNumber
            value={total}
            className="mt-1 block text-2xl font-bold tabular-nums text-slate-900 dark:text-white"
          />
        </div>
      </div>

      {/* Filters */}
      <MotionStagger className="card p-4">
        <MotionItem className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <div className="mb-2 flex items-center justify-between gap-3">
              <label htmlFor="identity-search" className="eyebrow">
                Search directory
              </label>
              {hasFilters && (
                <button
                  type="button"
                  onClick={() => {
                    handleSearchChange("");
                    setDebouncedSearch("");
                    handleTypeChange("");
                  }}
                  className="btn-ghost px-2 py-1 text-xs"
                >
                  Clear filters
                </button>
              )}
            </div>
            <div className="relative">
              <svg
                className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 dark:text-slate-500"
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                id="identity-search"
                type="text"
                placeholder="Search by name, UPN, or app ID..."
                value={search}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="input-base w-full pl-10"
              />
            </div>
          </div>

          <Tooltip content="Filter identities by type" position="bottom">
            <div>
              <label htmlFor="identity-type-filter" className="eyebrow mb-2 block">
                Identity type
              </label>
              <select
                id="identity-type-filter"
                value={typeFilter}
                onChange={(e) => handleTypeChange(e.target.value)}
                aria-label="Filter by identity type"
                className="input-base min-w-52"
              >
                {TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          </Tooltip>
        </MotionItem>

        <MotionItem className="mt-4 flex flex-wrap gap-2">
          {TYPE_OPTIONS.map((opt) => (
            <button
              key={opt.value || "all"}
              type="button"
              onClick={() => handleTypeChange(opt.value)}
              className={clsx(
                "badge ring-1 transition-all",
                typeFilter === opt.value
                  ? opt.value
                    ? TYPE_FILTER_STYLES[opt.value]
                    : "bg-slate-900 text-white ring-slate-900 dark:bg-white dark:text-slate-900 dark:ring-white"
                  : "bg-slate-50 text-slate-600 ring-slate-200 hover:bg-slate-100 dark:bg-slate-800/60 dark:text-slate-300 dark:ring-slate-700 dark:hover:bg-slate-800",
              )}
            >
              {opt.label}
            </button>
          ))}
        </MotionItem>
      </MotionStagger>

      <MotionStagger>
        <MotionItem>
          <IdentityTable
            data={data?.items ?? []}
            total={total}
            page={page}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
            isLoading={isLoading}
          />
        </MotionItem>
      </MotionStagger>
    </div>
  );
}
