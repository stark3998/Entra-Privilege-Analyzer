import { useState } from "react";
import clsx from "clsx";

type SectionId =
  | "overview"
  | "getting-started"
  | "prerequisites"
  | "permissions"
  | "features"
  | "detections"
  | "compliance"
  | "api"
  | "roles"
  | "configuration";

interface TocItem {
  id: SectionId;
  label: string;
}

const TOC: TocItem[] = [
  { id: "overview", label: "Overview" },
  { id: "getting-started", label: "Getting Started" },
  { id: "prerequisites", label: "Prerequisites" },
  { id: "permissions", label: "Graph API Permissions" },
  { id: "features", label: "Features" },
  { id: "detections", label: "Detections & Anomalies" },
  { id: "compliance", label: "Compliance Frameworks" },
  { id: "api", label: "API Reference" },
  { id: "roles", label: "App Roles & Access" },
  { id: "configuration", label: "Configuration" },
];

function Badge({ children, color = "blue" }: { children: React.ReactNode; color?: "blue" | "green" | "amber" | "red" | "purple" | "slate" }) {
  const colors = {
    blue: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
    green: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
    amber: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
    red: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
    purple: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
    slate: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  };
  return (
    <span className={clsx("inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium", colors[color])}>
      {children}
    </span>
  );
}

function SectionHeading({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="scroll-mt-20 border-b border-slate-200 pb-2 text-xl font-bold text-slate-900 dark:border-slate-700 dark:text-white">
      {children}
    </h2>
  );
}

function SubHeading({ children }: { children: React.ReactNode }) {
  return <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">{children}</h3>;
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-400">{children}</p>;
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-mono text-slate-700 dark:bg-slate-800 dark:text-slate-300">
      {children}
    </code>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs leading-relaxed text-slate-300">
      <code>{children}</code>
    </pre>
  );
}

function Table({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="bg-slate-50 dark:bg-slate-800/60">
            {headers.map((h) => (
              <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2 text-slate-700 dark:text-slate-300">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FeatureCard({ title, description, badges }: { title: string; description: string; badges: { label: string; color: "blue" | "green" | "amber" | "red" | "purple" | "slate" }[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md dark:border-slate-700 dark:bg-slate-800/50">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-slate-900 dark:text-white">{title}</span>
        {badges.map((b) => (
          <Badge key={b.label} color={b.color}>{b.label}</Badge>
        ))}
      </div>
      <p className="text-xs leading-relaxed text-slate-500 dark:text-slate-400">{description}</p>
    </div>
  );
}

function OverviewSection() {
  return (
    <div className="space-y-4">
      <SectionHeading id="overview">Overview</SectionHeading>
      <P>
        Entra Permissions Analyzer is a multi-tenant SaaS platform that connects to Microsoft Entra ID
        tenants via Microsoft Graph API, analyzes audit and sign-in logs to build per-identity action
        profiles, recommends least-privilege roles, detects permission drift and behavioral anomalies,
        evaluates 50+ best-practice rules, and maps findings to compliance frameworks (CIS, NIST, SOC 2).
      </P>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "Identity Types", value: "4", sub: "Users, SPs, MIs, Groups" },
          { label: "Best Practice Rules", value: "50+", sub: "Across 9 categories" },
          { label: "Detection Types", value: "7", sub: "Drift, geo, velocity, peer" },
          { label: "Compliance Frameworks", value: "3", sub: "CIS, NIST, SOC 2" },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-3 dark:border-slate-700 dark:from-slate-800 dark:to-slate-800/50">
            <div className="text-2xl font-bold text-brand-600 dark:text-brand-400">{stat.value}</div>
            <div className="text-xs font-semibold text-slate-700 dark:text-slate-300">{stat.label}</div>
            <div className="text-[10px] text-slate-400">{stat.sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function GettingStartedSection() {
  return (
    <div className="space-y-4">
      <SectionHeading id="getting-started">Getting Started</SectionHeading>
      <SubHeading>Quick Start (Local Development)</SubHeading>
      <CodeBlock>{`# 1. Clone the repository
git clone https://github.com/stark3998/Entra-Privilege-Analyzer.git
cd Entra-Permissions-Analyzer

# 2. Copy environment file
cp .env.example .env

# 3. Start with Docker Compose (recommended)
docker-compose up

# Backend runs on http://localhost:8000
# Frontend runs on http://localhost:5173`}</CodeBlock>
      <P>
        Docker Compose starts the backend, frontend, and Redis in <Code>LOCAL_MODE</Code> with
        authentication disabled. No Azure subscription is needed for local development.
      </P>
      <SubHeading>Manual Setup</SubHeading>
      <CodeBlock>{`# Backend
cd backend
pip install -e ".[dev]"
LOCAL_MODE=true uvicorn app.main:app --reload --port 8000

# Frontend (in a separate terminal)
cd frontend
npm install
VITE_LOCAL_MODE=true npm run dev`}</CodeBlock>
      <SubHeading>First Scan</SubHeading>
      <P>
        1. Create a project from the Projects page and provide your Entra ID app registration credentials.
        2. Navigate into the project and click "Run Scan" from the Scans page.
        3. The scan ingests audit logs, sign-in logs, PIM roles, users, service principals, groups,
        conditional access policies, MFA data, and risk detections from your tenant.
        4. After the scan completes, the Dashboard, Analytics, and all analysis pages populate automatically.
      </P>
    </div>
  );
}

function PrerequisitesSection() {
  return (
    <div className="space-y-4">
      <SectionHeading id="prerequisites">Prerequisites</SectionHeading>
      <SubHeading>Development</SubHeading>
      <Table
        headers={["Tool", "Version", "Purpose"]}
        rows={[
          ["Python", "3.12+", "Backend runtime"],
          ["Node.js", "20+", "Frontend build and dev server"],
          ["Docker + Compose", "Latest", "Local development environment"],
          ["Git", "Latest", "Source control"],
        ]}
      />
      <SubHeading>Production Deployment</SubHeading>
      <Table
        headers={["Resource", "SKU", "Purpose"]}
        rows={[
          ["Azure Container Apps", "Consumption", "Backend + frontend hosting"],
          ["Azure Cosmos DB", "Serverless", "NoSQL database (18 containers)"],
          ["Azure Cache for Redis", "Standard C1", "Dashboard cache, rate limiting"],
          ["Azure Key Vault", "Standard", "Secrets management (6 secrets)"],
          ["Azure AI Foundry", "GPT-4o", "AI narrative generation (optional)"],
          ["Azure Container Registry", "Basic", "Container image storage"],
          ["Terraform", "1.5+", "Infrastructure as Code"],
        ]}
      />
      <SubHeading>Entra ID App Registration</SubHeading>
      <P>
        Register a multi-tenant application in Entra ID with the permissions listed in the
        Graph API Permissions section below. The app must expose an <Code>access_as_user</Code> scope
        and include redirect URIs for your deployment domain. Configure three app roles:
        SecurityEngineer, IAMAdmin, and Executive.
      </P>
    </div>
  );
}

function PermissionsSection() {
  return (
    <div className="space-y-4">
      <SectionHeading id="permissions">Graph API Permissions</SectionHeading>
      <SubHeading>Required Permissions</SubHeading>
      <Table
        headers={["Permission", "Type", "Purpose"]}
        rows={[
          ["AuditLog.Read.All", "Application", "Audit logs, sign-in logs, MFA registration reports"],
          ["Directory.Read.All", "Application", "Directory data, OAuth2 permission grants"],
          ["User.Read.All", "Application", "User profiles, guest enrichment"],
          ["Application.Read.All", "Application", "App registrations, credentials, owners"],
          ["RoleManagement.Read.Directory", "Application", "Role definitions, role assignments"],
          ["RoleManagement.Read.All", "Application", "PIM eligible + active schedule instances"],
          ["Policy.Read.All", "Application", "Conditional access policies, cross-tenant access"],
          ["GroupMember.Read.All", "Application", "Group membership, transitive members"],
        ]}
      />
      <SubHeading>Optional Permissions (License-Dependent)</SubHeading>
      <Table
        headers={["Permission", "License", "Purpose"]}
        rows={[
          ["IdentityRiskEvent.Read.All", "Entra ID P2", "Risky users, risk detections"],
          ["IdentityRiskyServicePrincipal.Read.All", "Workload ID Premium", "Risky service principals"],
          ["AccessReview.Read.All", "Entra ID Governance", "Access review definitions"],
        ]}
      />
      <P>
        The application gracefully degrades when optional permissions or licenses are unavailable.
        Identity Protection signals, risky SP detection, and access review coverage analysis
        are skipped with a warning logged.
      </P>
    </div>
  );
}

function FeaturesSection() {
  return (
    <div className="space-y-4">
      <SectionHeading id="features">Features</SectionHeading>

      <SubHeading>Identity & Access Analysis</SubHeading>
      <div className="grid gap-3 sm:grid-cols-2">
        <FeatureCard
          title="Identity Action Profiling"
          description="Ingests audit logs, sign-in logs, and activity logs. Builds per-identity action profiles for users, service principals, managed identities, and groups."
          badges={[{ label: "Core", color: "blue" }]}
        />
        <FeatureCard
          title="PIM-Aware Role Analysis"
          description="Fetches active and eligible PIM role assignments. Distinguishes direct, pim_eligible, pim_activated, and group assignment types."
          badges={[{ label: "Core", color: "blue" }, { label: "PIM", color: "purple" }]}
        />
        <FeatureCard
          title="Least-Privilege Recommender"
          description="Maps observed actions to required permissions. Recommends best-matching built-in roles (72 Entra + 57 Azure RBAC) or generates custom role definitions."
          badges={[{ label: "Core", color: "blue" }]}
        />
        <FeatureCard
          title="Access Path Analysis"
          description="Detects indirect privilege escalation chains: app owner to SP, group owner to role, SP owner to permissions, and implicit app admin paths."
          badges={[{ label: "Advanced", color: "purple" }]}
        />
      </div>

      <SubHeading>Service Principal & Workload Identity</SubHeading>
      <div className="grid gap-3 sm:grid-cols-2">
        <FeatureCard
          title="SP Permission Usage Analysis"
          description="Cross-references granted app permissions against actual API calls. Identifies SPs with permissions they never use."
          badges={[{ label: "New", color: "green" }]}
        />
        <FeatureCard
          title="SP Credential Hygiene"
          description="Detects expired credentials, stale secrets (>365 days), multiple active credentials, and unused credentials on service principals."
          badges={[{ label: "New", color: "green" }]}
        />
        <FeatureCard
          title="Managed Identity Analysis"
          description="Flags managed identities with admin roles, broad root-scope assignments, or overprivileged configurations."
          badges={[{ label: "New", color: "green" }]}
        />
        <FeatureCard
          title="Federation Credential Validation"
          description="Checks federated identity credentials (GitHub OIDC, K8s) for wildcard subjects, broad issuer trusts, and missing audience restrictions."
          badges={[{ label: "New", color: "green" }]}
        />
      </div>

      <SubHeading>OAuth & Consent Governance</SubHeading>
      <div className="grid gap-3 sm:grid-cols-2">
        <FeatureCard
          title="Risky Consent Grant Detection"
          description="Identifies delegated grants for high-risk scopes (Mail.ReadWrite, Files.ReadWrite.All), unverified publishers, and user-consented high-privilege apps."
          badges={[{ label: "New", color: "green" }]}
        />
        <FeatureCard
          title="Consent Policy Analysis"
          description="Validates tenant-level consent settings: whether user consent is unrestricted and whether admin consent workflow is configured."
          badges={[{ label: "New", color: "green" }]}
        />
      </div>

      <SubHeading>Identity Lifecycle</SubHeading>
      <div className="grid gap-3 sm:grid-cols-2">
        <FeatureCard
          title="Orphaned Account Detection"
          description="Flags disabled accounts that still hold active role assignments. Critical severity for disabled Global Administrators."
          badges={[{ label: "New", color: "green" }]}
        />
        <FeatureCard
          title="Offboarding Validation"
          description="Identifies recently disabled accounts that still have roles or group memberships, indicating incomplete offboarding."
          badges={[{ label: "New", color: "green" }]}
        />
        <FeatureCard
          title="Never-Used Account Detection"
          description="Flags accounts provisioned >30 days ago with no sign-in activity. Critical if the account holds admin roles."
          badges={[{ label: "New", color: "green" }]}
        />
      </div>

      <SubHeading>Reporting & Remediation</SubHeading>
      <div className="grid gap-3 sm:grid-cols-2">
        <FeatureCard
          title="Executive Reports"
          description="Generate PDF and PowerPoint reports with risk scores, compliance metrics, top risky identities, and AI-generated narrative summaries."
          badges={[{ label: "Core", color: "blue" }]}
        />
        <FeatureCard
          title="IaC Export"
          description="Export role recommendations as Terraform HCL, Bicep, or ARM JSON templates. Supports bulk export as ZIP for up to 500 identities."
          badges={[{ label: "Core", color: "blue" }]}
        />
        <FeatureCard
          title="Remediation Workflow"
          description="Request, approve, reject, and execute remediation actions via the Graph API OBO flow. Full audit trail stored in Cosmos DB."
          badges={[{ label: "Core", color: "blue" }]}
        />
        <FeatureCard
          title="AI Narratives"
          description="GPT-4o-powered natural language summaries: executive digests, identity risk summaries, drift explanations, and recommendation rationale."
          badges={[{ label: "AI", color: "amber" }]}
        />
      </div>
    </div>
  );
}

function DetectionsSection() {
  return (
    <div className="space-y-4">
      <SectionHeading id="detections">Detections & Anomalies</SectionHeading>
      <P>
        The detection engine combines multiple layers of behavioral analysis to surface anomalous
        identity activity, complementing the static best-practice rule engine.
      </P>
      <Table
        headers={["Detection", "Method", "Severity Thresholds"]}
        rows={[
          ["First-Seen Action", "Flags any action not in the identity's 30-day baseline", "Medium (first occurrence)"],
          ["Frequency Anomaly", "Z-score of daily action count vs rolling baseline", "z > 1.5 Low, z > 2.0 Medium, z > 3.0 High"],
          ["Time-of-Day Anomaly", "Flags actions outside the identity's normal working hours using hour-of-day histogram", "Based on hour distribution deviation"],
          ["Velocity / Burst", "Compares recent-hour action count to baseline hourly rate", "3x Medium, 5x High, 10x Critical"],
          ["Geo-Location Anomaly", "Sign-in from a country not in the identity's known locations", "High (new country)"],
          ["Impossible Travel", "Two sign-ins >500km apart within 1 hour (haversine distance)", "Critical"],
          ["Peer Group Deviation", "Z-score of action count vs role-based peer group mean", "z > 2 Medium, z > 3 High, z > 4 Critical"],
        ]}
      />

      <SubHeading>Best Practice Rules (50+ Checks)</SubHeading>
      <Table
        headers={["Category", "Rules", "Examples"]}
        rows={[
          ["Identity Governance", "6", "Stale identity, permanent admin, no PIM, overprivileged, SoD, role-assignable group"],
          ["App Registration", "4", "Credential expiry, no owner, multi-tenant risk, excessive permissions"],
          ["MFA & Authentication", "3", "No MFA registered, weak MFA only, admin no phishing-resistant"],
          ["Guest / B2B", "4", "Guest admin, stale guest, pending invitation, guest no MFA"],
          ["Conditional Access", "12", "Legacy auth, MFA gaps, exclusion abuse, risk policies, device compliance"],
          ["Groups", "5", "Ownerless role-assignable, non-RA admin, dynamic admin, broad rules, large RA"],
          ["Custom Roles", "6", "Wildcards, escalation paths, built-in overlap, unused, no description, sprawl"],
          ["Access Reviews", "4", "Privileged roles uncovered, RA groups uncovered, stale reviews, no guest review"],
          ["Identity Lifecycle", "3", "Orphaned accounts, incomplete offboarding, never-used accounts"],
          ["SP & Workload", "6", "SP overprivileged, unused permissions, unused credential, MI overprivileged, federation"],
          ["OAuth Consent", "5", "Risky consent, unverified publisher, user consent high-privilege, unrestricted consent"],
        ]}
      />
    </div>
  );
}

function ComplianceSection() {
  return (
    <div className="space-y-4">
      <SectionHeading id="compliance">Compliance Frameworks</SectionHeading>
      <P>
        Every best-practice violation is automatically mapped to controls in three industry
        compliance frameworks. The compliance mapper computes per-framework scores and identifies
        which controls pass or fail based on active violations.
      </P>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800/50">
          <div className="text-sm font-semibold text-slate-900 dark:text-white">CIS Microsoft 365</div>
          <div className="text-xs text-slate-500 dark:text-slate-400">Foundations Benchmark v3.1.0</div>
          <div className="mt-2 text-2xl font-bold text-blue-600 dark:text-blue-400">23</div>
          <div className="text-xs text-slate-400">controls mapped</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800/50">
          <div className="text-sm font-semibold text-slate-900 dark:text-white">NIST SP 800-53</div>
          <div className="text-xs text-slate-500 dark:text-slate-400">Rev. 5</div>
          <div className="mt-2 text-2xl font-bold text-emerald-600 dark:text-emerald-400">22</div>
          <div className="text-xs text-slate-400">controls mapped</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800/50">
          <div className="text-sm font-semibold text-slate-900 dark:text-white">SOC 2 Type II</div>
          <div className="text-xs text-slate-500 dark:text-slate-400">Trust Services Criteria 2017</div>
          <div className="mt-2 text-2xl font-bold text-purple-600 dark:text-purple-400">14</div>
          <div className="text-xs text-slate-400">controls mapped</div>
        </div>
      </div>
      <P>
        Use the Reports page to generate per-framework compliance evidence reports in PDF format,
        with control-level pass/fail status and linked violation details.
      </P>
    </div>
  );
}

function ApiSection() {
  return (
    <div className="space-y-4">
      <SectionHeading id="api">API Reference</SectionHeading>
      <P>
        All project-scoped endpoints are under <Code>/api/projects/{"{project_id}"}/...</Code> and
        require a valid Bearer JWT token. The interactive OpenAPI docs are available at <Code>/docs</Code> (Swagger UI)
        and <Code>/redoc</Code> (ReDoc) on the backend.
      </P>

      <SubHeading>Dashboard & Analytics</SubHeading>
      <Table
        headers={["Method", "Endpoint", "Description"]}
        rows={[
          ["GET", "/dashboard", "Risk score, identity counts, compliance summary"],
          ["GET", "/dashboard/trends", "30-day time-series data for charts"],
          ["GET", "/analytics?days=30", "14 analytics widgets (activity, permissions, security posture)"],
        ]}
      />

      <SubHeading>Identities & Actions</SubHeading>
      <Table
        headers={["Method", "Endpoint", "Description"]}
        rows={[
          ["GET", "/identities", "Paginated, filterable identity list"],
          ["GET", "/identities/{id}", "Identity detail with PIM roles, risk, group memberships"],
          ["GET", "/identities/{id}/actions", "Action history timeline"],
        ]}
      />

      <SubHeading>Recommendations & Exports</SubHeading>
      <Table
        headers={["Method", "Endpoint", "Description"]}
        rows={[
          ["GET", "/recommendations", "Paginated recommendation list"],
          ["GET", "/recommendations/{id}", "Recommendation detail per identity"],
          ["POST", "/recommendations/compute", "Trigger batch computation (202 Accepted)"],
          ["GET", "/exports/{id}?format=terraform|bicep|arm", "Export IaC for an identity"],
          ["POST", "/exports/bulk", "Bulk export (max 500 identities, returns ZIP)"],
        ]}
      />

      <SubHeading>Drift Detection</SubHeading>
      <Table
        headers={["Method", "Endpoint", "Description"]}
        rows={[
          ["GET", "/drift-alerts", "Filterable drift alert list"],
          ["GET", "/drift-alerts/{id}", "Alert detail with evidence"],
          ["PATCH", "/drift-alerts/{id}", "Update status (acknowledge/escalate/resolve)"],
          ["POST", "/drift-alerts/detect", "Trigger on-demand detection (202 Accepted)"],
          ["GET", "/baselines/{id}", "View baseline statistics for an identity"],
        ]}
      />

      <SubHeading>Best Practices & Compliance</SubHeading>
      <Table
        headers={["Method", "Endpoint", "Description"]}
        rows={[
          ["GET", "/best-practices", "Filterable violation list (50+ types)"],
          ["GET", "/best-practices/summary", "Aggregated compliance score"],
          ["GET", "/best-practices/{id}", "Violation detail with remediation steps"],
          ["POST", "/best-practices/evaluate", "Trigger full evaluation (202 Accepted)"],
        ]}
      />

      <SubHeading>Remediation, Reports & Settings</SubHeading>
      <Table
        headers={["Method", "Endpoint", "Description"]}
        rows={[
          ["POST", "/remediation/request", "Request a new remediation action"],
          ["POST", "/remediation/{id}/approve", "Approve a pending action"],
          ["GET", "/reports/executive?format=pdf|pptx", "Download executive report"],
          ["GET", "/reports/compliance?framework=soc2|nist80053|cis_m365", "Compliance evidence report"],
          ["POST", "/sync/trigger", "Trigger Graph API data sync"],
          ["GET", "/narratives/executive", "AI-generated executive digest"],
        ]}
      />

      <SubHeading>System Endpoints</SubHeading>
      <Table
        headers={["Method", "Endpoint", "Description"]}
        rows={[
          ["GET", "/healthz", "Liveness probe"],
          ["GET", "/readyz", "Readiness probe (checks Cosmos DB connectivity)"],
        ]}
      />
    </div>
  );
}

function RolesSection() {
  return (
    <div className="space-y-4">
      <SectionHeading id="roles">App Roles & Access</SectionHeading>
      <P>
        Three application roles control access to different areas of the application.
        Users are assigned roles through the Entra ID app registration.
      </P>
      <Table
        headers={["Role", "Access", "Typical User"]}
        rows={[
          ["SecurityEngineer", "Drift alerts, identity deep-dive, action timeline, baselines, PIM sessions, access paths", "SOC analyst, security operations"],
          ["IAMAdmin", "Recommendations, IaC exports, best practices, settings, scan triggers, remediation, alert rules", "IAM team lead, identity admin"],
          ["Executive", "Dashboard, summary views, reports, AI narratives, analytics", "CISO, VP of Security, compliance officer"],
        ]}
      />
      <SubHeading>Project-Level Roles</SubHeading>
      <P>
        Within each project, members can be assigned viewer, operator, or admin roles.
        The project owner is implicitly an admin. Project access is validated on every
        API request — users can only access projects they are members of.
      </P>
    </div>
  );
}

function ConfigurationSection() {
  return (
    <div className="space-y-4">
      <SectionHeading id="configuration">Configuration</SectionHeading>
      <SubHeading>Backend Environment Variables</SubHeading>
      <Table
        headers={["Variable", "Required", "Default", "Description"]}
        rows={[
          ["LOCAL_MODE", "No", "false", "Skip auth, return mock user (dev only)"],
          ["AZURE_CLIENT_ID", "Prod", "", "Entra ID application client ID"],
          ["AZURE_CLIENT_SECRET", "Prod", "", "Entra ID client secret"],
          ["AZURE_TENANT_ID", "Prod", "", "Entra ID tenant ID (for OBO flow)"],
          ["COSMOS_ENDPOINT", "Prod", "https://localhost:8081", "Cosmos DB account endpoint"],
          ["COSMOS_KEY", "Prod", "", "Cosmos DB access key"],
          ["REDIS_HOST", "No", "localhost", "Redis hostname"],
          ["REDIS_PORT", "No", "6379", "Redis port"],
          ["REDIS_PASSWORD", "Prod", "", "Redis password"],
          ["KEYVAULT_URL", "Prod", "", "Azure Key Vault URL"],
          ["AZURE_FOUNDRY_ENDPOINT", "No", "", "Azure AI Foundry endpoint"],
          ["AZURE_FOUNDRY_KEY", "No", "", "Azure AI Foundry API key"],
          ["AZURE_FOUNDRY_MODEL", "No", "gpt-4o", "AI model deployment name"],
          ["GRAPH_API_VERSION", "No", "beta", "Graph API version (beta or v1.0)"],
          ["CORS_ORIGINS", "No", "http://localhost:5173", "Comma-separated allowed origins"],
        ]}
      />
      <SubHeading>Frontend Environment Variables</SubHeading>
      <Table
        headers={["Variable", "Required", "Default", "Description"]}
        rows={[
          ["VITE_APP_CLIENT_ID", "Prod", "", "Entra ID application client ID"],
          ["VITE_TENANT_ID", "Prod", "common", "Entra ID tenant for MSAL authority"],
          ["VITE_API_BASE_URL", "No", "", "API override (empty = same-origin proxy)"],
          ["VITE_LOCAL_MODE", "No", "false", "Skip MSAL authentication (dev only)"],
        ]}
      />
    </div>
  );
}

export function DocsPage() {
  const [activeSection, setActiveSection] = useState<SectionId>("overview");

  const handleNavClick = (id: SectionId) => {
    setActiveSection(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="flex h-full min-h-0">
      {/* Sticky sidebar TOC */}
      <nav className="hidden w-52 shrink-0 overflow-y-auto border-r border-slate-200 px-3 py-6 dark:border-slate-700 lg:block">
        <p className="mb-3 px-2 text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
          Documentation
        </p>
        <ul className="space-y-0.5">
          {TOC.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => handleNavClick(item.id)}
                className={clsx(
                  "w-full rounded-lg px-2 py-1.5 text-left text-xs font-medium transition-colors",
                  activeSection === item.id
                    ? "bg-brand-50 text-brand-700 dark:bg-brand-950/50 dark:text-brand-300"
                    : "text-slate-500 hover:bg-slate-50 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-300",
                )}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Main content */}
      <main
        className="flex-1 overflow-y-auto px-6 py-6 lg:px-10"
        onScroll={(e) => {
          const container = e.currentTarget;
          for (const item of [...TOC].reverse()) {
            const el = document.getElementById(item.id);
            if (el && el.offsetTop - container.scrollTop <= 100) {
              setActiveSection(item.id);
              break;
            }
          }
        }}
      >
        <div className="mx-auto max-w-4xl space-y-10">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              Entra Permissions Analyzer
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Comprehensive documentation for setup, features, API reference, and configuration.
            </p>
          </div>

          <OverviewSection />
          <GettingStartedSection />
          <PrerequisitesSection />
          <PermissionsSection />
          <FeaturesSection />
          <DetectionsSection />
          <ComplianceSection />
          <ApiSection />
          <RolesSection />
          <ConfigurationSection />

          <div className="border-t border-slate-200 pt-6 dark:border-slate-700">
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Entra Permissions Analyzer v0.8.0 &middot; Powered by Microsoft Entra ID &middot; Built with FastAPI + React
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
