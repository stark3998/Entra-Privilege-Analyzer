// Central registry of project-scoped pages.
// Powers the Command Palette, global search, and Breadcrumbs so navigation
// metadata stays consistent across the app. Data-only (no JSX).

export type NavGroup = "Analyze" | "Govern" | "Manage";

export interface PageEntry {
  /** Path suffix under /projects/:projectId/ */
  suffix: string;
  label: string;
  group: NavGroup;
  description: string;
  keywords: string[];
  roles?: string[];
}

export const PAGE_REGISTRY: PageEntry[] = [
  { suffix: "dashboard", label: "Dashboard", group: "Analyze", description: "Executive overview of your permissions posture", keywords: ["home", "overview", "kpi", "summary", "executive"] },
  { suffix: "analytics", label: "Analytics", group: "Analyze", description: "Activity, permission, and security posture analytics", keywords: ["charts", "trends", "activity", "usage", "metrics"] },
  { suffix: "identities", label: "Identities", group: "Analyze", description: "Browse users, service principals, and groups", keywords: ["users", "service principals", "managed identities", "people", "accounts"] },
  { suffix: "recommendations", label: "Recommendations", group: "Analyze", description: "Least-privilege role suggestions from real usage", keywords: ["least privilege", "roles", "reduce", "advice", "suggestions"] },
  { suffix: "drift", label: "Drift Monitor", group: "Analyze", description: "Anomalous permission usage and first-seen actions", keywords: ["anomaly", "alerts", "changes", "deviation"] },
  { suffix: "pim-sessions", label: "PIM Sessions", group: "Analyze", description: "Privileged role activations and session activity", keywords: ["privileged", "elevation", "activation", "jit"] },
  { suffix: "best-practices", label: "Best Practices", group: "Analyze", description: "Compliance against Entra ID best practices", keywords: ["violations", "compliance", "findings", "posture"] },
  { suffix: "app-registrations", label: "App Registrations", group: "Analyze", description: "App registrations, credentials, and risky permissions", keywords: ["apps", "credentials", "secrets", "certificates"] },
  { suffix: "conditional-access", label: "Conditional Access", group: "Analyze", description: "Conditional access policies and coverage", keywords: ["ca", "policies", "mfa", "conditions"] },
  { suffix: "groups", label: "Groups", group: "Analyze", description: "Group memberships, roles, and dynamic rules", keywords: ["membership", "dynamic", "security groups"] },
  { suffix: "access-paths", label: "Access Paths", group: "Analyze", description: "Indirect privilege escalation chains", keywords: ["escalation", "graph", "attack path", "lateral"] },
  { suffix: "custom-roles", label: "Custom Roles", group: "Analyze", description: "Custom role definitions and escalation risks", keywords: ["wildcards", "definitions", "rbac"] },

  { suffix: "workflows", label: "Workflow Inbox", group: "Govern", description: "Triage approvals, escalations, and governance workflows", keywords: ["approvals", "inbox", "tasks", "escalations"], roles: ["SecurityEngineer", "IAMAdmin"] },
  { suffix: "evidence", label: "Evidence Explorer", group: "Govern", description: "Evidence coverage and workflow linkage", keywords: ["audit", "coverage", "proof", "records"], roles: ["SecurityEngineer", "IAMAdmin", "Executive"] },
  { suffix: "personas", label: "Persona Catalog", group: "Govern", description: "Governance personas, guardrails, and SLAs", keywords: ["roles", "guardrails", "sla", "templates"], roles: ["IAMAdmin", "Executive"] },
  { suffix: "copilot", label: "Scoped Copilot", group: "Govern", description: "Governed copilot prompts with scope boundaries", keywords: ["ai", "assistant", "prompt", "chat"], roles: ["SecurityEngineer", "IAMAdmin"] },

  { suffix: "connectors", label: "Connectors", group: "Manage", description: "Configured governance connectors and settings", keywords: ["integrations", "sources", "config"], roles: ["IAMAdmin"] },
  { suffix: "scan", label: "Scans", group: "Manage", description: "Run and monitor permission scans", keywords: ["sync", "ingest", "refresh", "collect"] },
  { suffix: "reports", label: "Reports", group: "Manage", description: "Download executive PDF and PowerPoint reports", keywords: ["pdf", "pptx", "export", "download"] },
  { suffix: "remediation", label: "Remediation", group: "Manage", description: "Track remediation actions and status", keywords: ["fix", "history", "actions"] },
  { suffix: "members", label: "Members", group: "Manage", description: "Manage team access and roles", keywords: ["team", "invite", "users", "access"] },
  { suffix: "settings", label: "Settings", group: "Manage", description: "Sync schedule and baseline window", keywords: ["config", "preferences", "schedule"] },
];

/** Human-friendly labels for URL segments used by breadcrumbs. */
export const SEGMENT_LABELS: Record<string, string> = Object.fromEntries(
  PAGE_REGISTRY.map((p) => [p.suffix, p.label]),
);

export function pageForSuffix(suffix: string): PageEntry | undefined {
  return PAGE_REGISTRY.find((p) => p.suffix === suffix);
}

export function visiblePages(roles: string[]): PageEntry[] {
  return PAGE_REGISTRY.filter(
    (p) => !p.roles || p.roles.some((r) => roles.includes(r)),
  );
}
