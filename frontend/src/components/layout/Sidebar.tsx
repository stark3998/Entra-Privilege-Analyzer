import { useLocation, Link } from "react-router-dom";
import clsx from "clsx";
import { Tooltip } from "@/components/common/Tooltip";
import { useProjectContext } from "@/store/projectContext";
import { useAuth } from "@/auth/useAuth";

interface NavItem {
  label: string;
  path: string;
  hint: string;
  icon: React.ReactNode;
  section: "analyze" | "manage";
  roles?: string[];
}

function useNavItems(): NavItem[] {
  const { projectId } = useProjectContext();
  const base = `/projects/${projectId}`;

  return [
    {
      label: "Dashboard",
      path: `${base}/dashboard`,
      hint: "Executive overview of your permissions posture",
      section: "analyze",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 5a1 1 0 011-1h4a1 1 0 011 1v5a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v3a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v3a1 1 0 01-1 1H5a1 1 0 01-1-1v-3zm10-1a1 1 0 011-1h4a1 1 0 011 1v5a1 1 0 01-1 1h-4a1 1 0 01-1-1v-5z" />
        </svg>
      ),
    },
    {
      label: "Analytics",
      path: `${base}/analytics`,
      hint: "Detailed activity, permission, and security posture analytics",
      section: "analyze",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
      ),
    },
    {
      label: "Workflow Inbox",
      path: `${base}/workflows`,
      hint: "Triage governance workflows, approvals, and escalations",
      section: "analyze",
      roles: ["SecurityEngineer", "IAMAdmin"],
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12c0 4.97-4.03 9-9 9s-9-4.03-9-9 4.03-9 9-9 9 4.03 9 9z" />
        </svg>
      ),
    },
    {
      label: "Evidence Explorer",
      path: `${base}/evidence`,
      hint: "Inspect evidence coverage and workflow linkage",
      section: "analyze",
      roles: ["SecurityEngineer", "IAMAdmin", "Executive"],
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-8.625a2.625 2.625 0 00-2.625-2.625H7.125A2.625 2.625 0 004.5 5.625v12.75A2.625 2.625 0 007.125 21h5.625m6.75-6.75H15a2.25 2.25 0 00-2.25 2.25V21m6.75-6.75L12.75 21" />
        </svg>
      ),
    },
    {
      label: "Persona Catalog",
      path: `${base}/personas`,
      hint: "Review governance personas, guardrails, and SLA expectations",
      section: "analyze",
      roles: ["IAMAdmin", "Executive"],
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6.75a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75a17.933 17.933 0 01-7.499-1.632z" />
        </svg>
      ),
    },
    {
      label: "Scoped Copilot",
      path: `${base}/copilot`,
      hint: "Run governed copilot prompts with explicit scope boundaries",
      section: "analyze",
      roles: ["SecurityEngineer", "IAMAdmin"],
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-2.844.813a1.125 1.125 0 000 2.124L9 22.5l.813 2.844a1.125 1.125 0 002.124 0L12.75 22.5l2.844-.813a1.125 1.125 0 000-2.124L12.75 18.75l-.813-2.846a1.125 1.125 0 00-2.124 0z" transform="translate(3 -3)" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 9.75L6 12l2.25.75L6 13.5l-.75 2.25L4.5 13.5l-2.25-.75L4.5 12l.75-2.25zM18 4.5l.375 1.125L19.5 6l-1.125.375L18 7.5l-.375-1.125L16.5 6l1.125-.375L18 4.5z" />
        </svg>
      ),
    },
    {
      label: "Identities",
      path: `${base}/identities`,
      hint: "Browse all Entra ID users, service principals, and groups",
      section: "analyze",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
    },
    {
      label: "Recommendations",
      path: `${base}/recommendations`,
      hint: "Least-privilege role suggestions based on actual usage",
      section: "analyze",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
      ),
    },
    {
      label: "Drift Monitor",
      path: `${base}/drift`,
      hint: "Detect anomalous permission usage and first-seen actions",
      section: "analyze",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      ),
    },
    {
      label: "PIM Sessions",
      path: `${base}/pim-sessions`,
      hint: "Track privileged role activations and session activity",
      section: "analyze",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      label: "Best Practices",
      path: `${base}/best-practices`,
      hint: "Evaluate against Entra ID security best practices",
      section: "analyze",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      label: "App Registrations",
      path: `${base}/app-registrations`,
      hint: "Review app registrations, credentials, and high-risk permissions",
      section: "analyze",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
        </svg>
      ),
    },
    {
      label: "Conditional Access",
      path: `${base}/conditional-access`,
      hint: "Review conditional access policies and their coverage",
      section: "analyze",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
      ),
    },
    {
      label: "Groups",
      path: `${base}/groups`,
      hint: "Inspect group memberships, role assignments, and dynamic rules",
      section: "analyze",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
      ),
    },
    {
      label: "Access Paths",
      path: `${base}/access-paths`,
      hint: "Detect indirect privilege escalation chains",
      section: "analyze",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
        </svg>
      ),
    },
    {
      label: "Custom Roles",
      path: `${base}/custom-roles`,
      hint: "Audit custom role definitions for wildcards and escalation paths",
      section: "analyze",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
      ),
    },
    {
      label: "Connectors",
      path: `${base}/connectors`,
      hint: "Inspect configured governance connectors and their stored settings",
      section: "manage",
      roles: ["IAMAdmin"],
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 12h12M6 12a2.25 2.25 0 100-4.5A2.25 2.25 0 006 12zm12 4.5A2.25 2.25 0 1018 12a2.25 2.25 0 000 4.5zM6 21a2.25 2.25 0 100-4.5A2.25 2.25 0 006 21z" />
        </svg>
      ),
    },
    {
      label: "Scans",
      path: `${base}/scan`,
      hint: "Run and monitor permission scans",
      section: "manage",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      ),
    },
    {
      label: "Reports",
      path: `${base}/reports`,
      hint: "Download executive PDF and PowerPoint reports",
      section: "manage",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
      ),
    },
    {
      label: "Remediation",
      path: `${base}/remediation`,
      hint: "Track remediation actions and their status",
      section: "manage",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17l-5.1-5.1m0 0L11.42 4.97m-5.1 5.1H21M3 3v18" />
        </svg>
      ),
    },
    {
      label: "Members",
      path: `${base}/members`,
      hint: "Manage team access and roles",
      section: "manage",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
        </svg>
      ),
    },
    {
      label: "Settings",
      path: `${base}/settings`,
      hint: "Configure sync schedule and baseline window",
      section: "manage",
      icon: (
        <svg className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
    },
  ];
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-1 mt-6 px-3 text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
      {children}
    </p>
  );
}

export function Sidebar() {
  const location = useLocation();
  const { roles } = useAuth();
  const navItems = useNavItems();
  const visibleItems = navItems.filter(
    (item) => !item.roles || item.roles.some((role) => roles.includes(role)),
  );

  const analyzeItems = visibleItems.filter((i) => i.section === "analyze");
  const manageItems = visibleItems.filter((i) => i.section === "manage");

  return (
    <aside className="flex min-h-0 w-60 flex-col border-r border-slate-200/80 bg-white dark:border-slate-700/80 dark:bg-slate-900">
      <nav className="flex-1 overflow-y-auto px-3 py-2">
        {/* Back to projects */}
        <Link
          to="/projects"
          className="mb-2 flex items-center gap-2 rounded-xl px-3 py-2 text-[12px] font-medium text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-slate-200"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          All Projects
        </Link>

        {analyzeItems.length > 0 && (
          <>
            <SectionLabel>Analyze</SectionLabel>
            <div className="space-y-0.5">
              {analyzeItems.map((item) => {
                const isActive =
                  location.pathname === item.path ||
                  (item.path !== "/" && location.pathname.startsWith(item.path + "/"));
                return (
                  <Tooltip key={item.path} content={item.hint} position="right" delay={400}>
                    <Link
                      to={item.path}
                      className={clsx(
                        "group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-all duration-200",
                        isActive
                          ? "bg-brand-50 text-brand-700 shadow-sm dark:bg-brand-950/50 dark:text-brand-300"
                          : "text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-slate-200",
                      )}
                    >
                      <span
                        className={clsx(
                          "flex h-8 w-8 items-center justify-center rounded-lg transition-colors",
                          isActive
                            ? "bg-brand-100 text-brand-600 dark:bg-brand-900/40 dark:text-brand-400"
                            : "bg-slate-100 text-slate-500 group-hover:bg-slate-200 group-hover:text-slate-700 dark:bg-slate-800 dark:text-slate-400 dark:group-hover:bg-slate-700 dark:group-hover:text-slate-300",
                        )}
                      >
                        {item.icon}
                      </span>
                      <span>{item.label}</span>
                      {isActive && (
                        <span className="ml-auto h-1.5 w-1.5 rounded-full bg-brand-500" />
                      )}
                    </Link>
                  </Tooltip>
                );
              })}
            </div>
          </>
        )}

        {manageItems.length > 0 && (
          <>
            <SectionLabel>Manage</SectionLabel>
            <div className="space-y-0.5">
              {manageItems.map((item) => {
                const isActive =
                  location.pathname === item.path ||
                  (item.path !== "/" && location.pathname.startsWith(item.path + "/"));
                return (
                  <Tooltip key={item.path} content={item.hint} position="right" delay={400}>
                    <Link
                      to={item.path}
                      className={clsx(
                        "group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-all duration-200",
                        isActive
                          ? "bg-brand-50 text-brand-700 shadow-sm dark:bg-brand-950/50 dark:text-brand-300"
                          : "text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-slate-200",
                      )}
                    >
                      <span
                        className={clsx(
                          "flex h-8 w-8 items-center justify-center rounded-lg transition-colors",
                          isActive
                            ? "bg-brand-100 text-brand-600 dark:bg-brand-900/40 dark:text-brand-400"
                            : "bg-slate-100 text-slate-500 group-hover:bg-slate-200 group-hover:text-slate-700 dark:bg-slate-800 dark:text-slate-400 dark:group-hover:bg-slate-700 dark:group-hover:text-slate-300",
                        )}
                      >
                        {item.icon}
                      </span>
                      <span>{item.label}</span>
                      {isActive && (
                        <span className="ml-auto h-1.5 w-1.5 rounded-full bg-brand-500" />
                      )}
                    </Link>
                  </Tooltip>
                );
              })}
            </div>
          </>
        )}

      </nav>

      {/* Footer */}
      <div className="border-t border-slate-200/80 px-3 py-3 dark:border-slate-700/80">
        <Link
          to="/docs"
          target="_blank"
          className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-[11px] font-medium text-slate-400 transition-colors hover:bg-slate-50 hover:text-slate-600 dark:text-slate-500 dark:hover:bg-slate-800 dark:hover:text-slate-300"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
          Documentation
        </Link>
        <p className="mt-1 px-2 text-[10px] font-medium text-slate-400 dark:text-slate-500">
          Powered by Microsoft Entra ID
        </p>
      </div>
    </aside>
  );
}
