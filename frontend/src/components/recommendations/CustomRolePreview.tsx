// frontend/src/components/recommendations/CustomRolePreview.tsx
import { useState, useMemo } from "react";
import clsx from "clsx";
import type { CustomRoleDefinition } from "@/api/types";
import { JsonViewer } from "@/components/common/JsonViewer";

interface CustomRolePreviewProps {
  customRole: CustomRoleDefinition;
}

type RoleScope = "entra" | "azure";

/**
 * Displays a custom role definition in a JSON viewer with
 * a tab toggle between Entra Custom Role and Azure Custom Role formats.
 *
 * Usage:
 * ```tsx
 * <CustomRolePreview customRole={rec.custom_role} />
 * ```
 */
export function CustomRolePreview({ customRole }: CustomRolePreviewProps) {
  // Determine the initial tab from the role scope
  const initialScope: RoleScope = customRole.scope.toLowerCase().includes("azure")
    ? "azure"
    : "entra";
  const [activeTab, setActiveTab] = useState<RoleScope>(initialScope);

  const jsonContent = useMemo(() => {
    if (activeTab === "azure" && !Array.isArray(customRole.permissions)) {
      // Azure RBAC format with actions/dataActions
      return JSON.stringify(
        {
          Name: customRole.name,
          Description: customRole.description,
          IsCustom: true,
          AssignableScopes: customRole.is_assignable_scopes,
          Permissions: [customRole.permissions],
        },
        null,
        2,
      );
    }

    // Entra format with flat permission strings
    const permissions = Array.isArray(customRole.permissions)
      ? customRole.permissions
      : [
          ...customRole.permissions.actions,
          ...customRole.permissions.dataActions,
        ];

    return JSON.stringify(
      {
        displayName: customRole.name,
        description: customRole.description,
        isEnabled: true,
        rolePermissions: [
          {
            allowedResourceActions: permissions,
          },
        ],
      },
      null,
      2,
    );
  }, [customRole, activeTab]);

  const tabs: { key: RoleScope; label: string }[] = [
    { key: "entra", label: "Entra Custom Role" },
    { key: "azure", label: "Azure Custom Role" },
  ];

  return (
    <div className="space-y-3">
      {/* Tab toggle */}
      <div className="flex gap-1 rounded-lg border border-slate-200 bg-slate-100 p-1 dark:border-slate-700 dark:bg-slate-800">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={clsx(
              "flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              activeTab === tab.key
                ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white"
                : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Role summary */}
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/50">
        <p className="text-sm font-medium text-slate-900 dark:text-white">
          {customRole.name}
        </p>
        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
          {customRole.description}
        </p>
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
          Assignable scopes: {customRole.is_assignable_scopes.join(", ") || "None"}
        </p>
      </div>

      {/* JSON viewer */}
      <JsonViewer content={jsonContent} language="json" maxHeight="max-h-80" />
    </div>
  );
}
