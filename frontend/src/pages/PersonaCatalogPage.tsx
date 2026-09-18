import { useMemo, useState } from "react";
import { usePersonaCatalog } from "@/api/hooks";
import { GovernanceErrorState } from "@/components/governance/GovernanceFeedback";
import { GovernanceMetricCard } from "@/components/governance/GovernanceMetricCard";
import { PersonaCatalogGrid } from "@/components/governance/PersonaCatalogGrid";
import { MotionItem, MotionStagger } from "@/components/common/motion";

export function PersonaCatalogPage() {
  const [search, setSearch] = useState("");
  const { data, isLoading, isError, error } = usePersonaCatalog();

  const personas = useMemo(() => {
    const items = data ?? [];
    if (!search.trim()) return items;
    const needle = search.trim().toLowerCase();
    return items.filter(
      (persona) =>
        persona.name.toLowerCase().includes(needle) ||
        persona.id.toLowerCase().includes(needle) ||
        (persona.builtin_role_name ?? "").toLowerCase().includes(needle) ||
        persona.common_permissions.some((item) => item.toLowerCase().includes(needle)) ||
        persona.justified_rare_permissions.some((item) => item.toLowerCase().includes(needle)) ||
        persona.escalation_findings.some((item) => item.toLowerCase().includes(needle)) ||
        persona.sod_findings.some((item) => item.toLowerCase().includes(needle)),
    );
  }, [data, search]);

  if (isError) {
    return <GovernanceErrorState error={error} feature="persona catalog" />;
  }

  const publishedCount = (data ?? []).filter((persona) => persona.status === "published").length;
  const approvedCount = (data ?? []).filter((persona) =>
    ["approved", "published"].includes(persona.status),
  ).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Governance Personas</p>
          <h1 className="page-title mt-1">Persona Catalog</h1>
          <p className="page-subtitle">
            Review raw persona records, permission baselines, and approval state from the governance backend
          </p>
        </div>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="input-base min-w-72 py-2"
          placeholder="Search persona IDs, roles, or findings"
          aria-label="Search personas"
        />
      </div>

      <MotionStagger className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <MotionItem><GovernanceMetricCard label="Personas" value={(data ?? []).length} tone="brand" /></MotionItem>
        <MotionItem><GovernanceMetricCard label="Approved or published" value={approvedCount} tone="emerald" /></MotionItem>
        <MotionItem><GovernanceMetricCard label="Published" value={publishedCount} tone="slate" caption={isLoading ? "Loading..." : "Current backend records"} /></MotionItem>
      </MotionStagger>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="card p-5">
              <div className="skeleton h-4 w-1/4" />
              <div className="skeleton mt-3 h-6 w-2/3" />
              <div className="skeleton mt-4 h-20" />
            </div>
          ))}
        </div>
      ) : (
        <PersonaCatalogGrid personas={personas} />
      )}
    </div>
  );
}
