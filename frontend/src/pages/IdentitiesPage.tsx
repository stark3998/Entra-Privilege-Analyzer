import { useState, useEffect, useCallback, useRef } from "react";
import { useIdentities } from "@/api/hooks";
import { IdentityTable } from "@/components/identities/IdentityTable";
import { Tooltip } from "@/components/common/Tooltip";
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

export function IdentitiesPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<IdentityType | "">("");
  const [page, setPage] = useState(1);

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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Identities</h1>
        <p className="page-subtitle">
          Browse and inspect all Entra ID identities, their roles, and activity
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <svg
            className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search by name, UPN, or app ID..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="input-base w-full pl-10"
          />
        </div>

        <Tooltip content="Filter identities by type" position="bottom">
          <select
            value={typeFilter}
            onChange={(e) => handleTypeChange(e.target.value)}
            aria-label="Filter by identity type"
            className="input-base"
          >
            {TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </Tooltip>
      </div>

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
