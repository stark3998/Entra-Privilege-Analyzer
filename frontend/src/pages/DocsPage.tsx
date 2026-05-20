import { useState, useMemo, useRef, useCallback, useEffect } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";

// ---------------------------------------------------------------------------
// Search index — each entry has an id (section), title, and searchable text
// ---------------------------------------------------------------------------

interface SearchEntry {
  section: SectionId;
  title: string;
  text: string;
}

const SEARCH_INDEX: SearchEntry[] = [
  {
    section: "overview",
    title: "Overview",
    text: "Entra Permissions Analyzer multi-tenant SaaS Microsoft Entra ID Graph API audit sign-in logs identity action profiles least-privilege roles permission drift behavioral anomalies 50+ best-practice rules compliance frameworks CIS NIST SOC 2 identity types users service principals managed identities groups detection types drift geo velocity peer",
  },
  {
    section: "getting-started",
    title: "Getting Started",
    text: "clone repository docker compose local mode LOCAL_MODE authentication disabled pip install uvicorn npm run dev quick start backend frontend Redis first scan project create scan ingest audit logs sign-in logs PIM roles conditional access MFA risk detections",
  },
  {
    section: "prerequisites",
    title: "Prerequisites",
    text: "Python 3.12 Node.js 20 Docker Compose Terraform Azure Container Apps Cosmos DB Redis Key Vault AI Foundry GPT-4o Container Registry Entra ID app registration access_as_user scope redirect URIs SecurityEngineer IAMAdmin Executive",
  },
  {
    section: "permissions",
    title: "Graph API Permissions",
    text: "AuditLog.Read.All Directory.Read.All User.Read.All Application.Read.All RoleManagement.Read.Directory RoleManagement.Read.All Policy.Read.All GroupMember.Read.All IdentityRiskEvent.Read.All IdentityRiskyServicePrincipal.Read.All AccessReview.Read.All Entra ID P2 Workload ID Premium Governance license-dependent gracefully degrades",
  },
  {
    section: "features",
    title: "Features",
    text: "Identity Action Profiling audit logs sign-in activity PIM-Aware Role Analysis eligible activated direct group Least-Privilege Recommender built-in roles custom role definitions Access Path Analysis privilege escalation SP Permission Usage Analysis granted observed unused overprivileged SP Credential Hygiene expired stale multiple active Managed Identity Analysis admin roles broad scope Federation Credential Validation GitHub OIDC Kubernetes wildcard subjects audience Risky Consent Grant Detection Mail.ReadWrite Files.ReadWrite.All unverified publisher Consent Policy Analysis user consent unrestricted admin consent workflow Orphaned Account Detection disabled role assignments Offboarding Validation incomplete offboarding Never-Used Account Detection provisioned no sign-in Executive Reports PDF PowerPoint IaC Export Terraform Bicep ARM Remediation Workflow approve reject OBO AI Narratives GPT-4o executive digest",
  },
  {
    section: "detections",
    title: "Detections & Anomalies",
    text: "First-Seen Action baseline Frequency Anomaly z-score Time-of-Day Anomaly hour histogram working hours Velocity Burst recent-hour action rate 3x 5x 10x Geo-Location Anomaly country known locations Impossible Travel 500km haversine distance Peer Group Deviation role-based peer group mean identity governance stale permanent admin no PIM overprivileged separation of duties role-assignable group app registration credential expiry no owner multi-tenant excessive permissions MFA authentication weak phishing-resistant guest B2B conditional access legacy auth device compliance groups custom roles wildcards escalation access reviews SP workload unused credential managed identity federation OAuth consent risky unverified publisher",
  },
  {
    section: "compliance",
    title: "Compliance Frameworks",
    text: "CIS Microsoft 365 Foundations Benchmark v3.1.0 23 controls NIST SP 800-53 Rev 5 22 controls SOC 2 Type II Trust Services Criteria 2017 14 controls compliance mapper per-framework scores pass fail violation IDs evidence reports PDF control-level",
  },
  {
    section: "api",
    title: "API Reference",
    text: "GET POST PATCH /api/projects project_id Bearer JWT OpenAPI Swagger ReDoc dashboard trends analytics identities actions recommendations compute exports terraform bicep arm drift-alerts detect baselines best-practices summary evaluate remediation request approve reports executive compliance sync trigger narratives healthz readyz liveness readiness",
  },
  {
    section: "roles",
    title: "App Roles & Access",
    text: "SecurityEngineer drift alerts identity deep-dive action timeline baselines PIM sessions access paths IAMAdmin recommendations IaC exports best practices settings scan triggers remediation alert rules Executive dashboard summary views reports AI narratives analytics viewer operator admin project-level roles project owner member",
  },
  {
    section: "configuration",
    title: "Configuration",
    text: "LOCAL_MODE AZURE_CLIENT_ID AZURE_CLIENT_SECRET AZURE_TENANT_ID COSMOS_ENDPOINT COSMOS_KEY REDIS_HOST REDIS_PORT REDIS_PASSWORD KEYVAULT_URL AZURE_FOUNDRY_ENDPOINT AZURE_FOUNDRY_KEY AZURE_FOUNDRY_MODEL GRAPH_API_VERSION CORS_ORIGINS VITE_APP_CLIENT_ID VITE_TENANT_ID VITE_API_BASE_URL VITE_LOCAL_MODE environment variables backend frontend",
  },
];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

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
    <h2 id={id} className="scroll-mt-24 border-b border-slate-200 pb-2 text-xl font-bold text-slate-900 dark:border-slate-700 dark:text-white">
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

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

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
          { label: "Best Practice Rules", value: "50+", sub: "Across 11 categories" },
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
      <SubHeading>Verify Installation</SubHeading>
      <Table
        headers={["Check", "URL", "Expected"]}
        rows={[
          ["Backend health", "http://localhost:8000/healthz", '{"status": "ok"}'],
          ["Backend readiness", "http://localhost:8000/readyz", '{"status": "ready"} or {"status": "not_ready"}'],
          ["API docs (Swagger)", "http://localhost:8000/docs", "Interactive OpenAPI documentation"],
          ["Frontend", "http://localhost:5173", "Projects page (or login gate)"],
        ]}
      />
      <SubHeading>First Scan</SubHeading>
      <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4 dark:border-blue-800 dark:bg-blue-900/20">
        <ol className="ml-4 list-decimal space-y-2 text-sm text-slate-700 dark:text-slate-300">
          <li>Create a project from the <strong>Projects</strong> page — provide your Entra ID app registration client ID and secret.</li>
          <li>Navigate into the project and go to <strong>Scans</strong> &rarr; click <strong>Run Scan</strong>.</li>
          <li>The scan ingests audit logs, sign-in logs, PIM roles, users, service principals, groups, conditional access policies, MFA data, and risk detections from your tenant.</li>
          <li>After the scan completes, <strong>Dashboard</strong>, <strong>Analytics</strong>, and all analysis pages populate automatically.</li>
          <li>Configure a <strong>scan schedule</strong> in Settings for automatic recurring scans (default: every 6 hours).</li>
        </ol>
      </div>
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
          ["Azure Cache for Redis", "Standard C1", "Dashboard cache, rate limiting, scan event streaming"],
          ["Azure Key Vault", "Standard", "Secrets management (6 secrets)"],
          ["Azure AI Foundry", "GPT-4o", "AI narrative generation (optional)"],
          ["Azure Container Registry", "Basic", "Container image storage"],
          ["Terraform", "1.5+", "Infrastructure as Code"],
        ]}
      />
      <SubHeading>Entra ID App Registration</SubHeading>
      <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-4 dark:border-amber-800 dark:bg-amber-900/20">
        <p className="mb-2 text-sm font-semibold text-amber-800 dark:text-amber-300">Required app registration setup:</p>
        <ul className="ml-4 list-disc space-y-1 text-sm text-slate-700 dark:text-slate-300">
          <li>Register a <strong>multi-tenant</strong> application in Entra ID</li>
          <li>Add all required Graph API permissions listed in the next section</li>
          <li>Expose an <Code>access_as_user</Code> delegated scope</li>
          <li>Add redirect URIs for your deployment domain (SPA type)</li>
          <li>Create three app roles: <Code>SecurityEngineer</Code>, <Code>IAMAdmin</Code>, <Code>Executive</Code></li>
          <li>Generate a client secret and store it securely (Key Vault in production)</li>
        </ul>
      </div>
    </div>
  );
}

function PermissionsSection() {
  return (
    <div className="space-y-4">
      <SectionHeading id="permissions">Graph API Permissions</SectionHeading>
      <SubHeading>Required Permissions</SubHeading>
      <P>
        These permissions must be granted admin consent in the target tenant for the scan to retrieve data.
      </P>
      <Table
        headers={["Permission", "Type", "Purpose"]}
        rows={[
          ["AuditLog.Read.All", "Application", "Audit logs, sign-in logs, MFA registration reports"],
          ["Directory.Read.All", "Application", "Directory data, OAuth2 permission grants"],
          ["User.Read.All", "Application", "User profiles, guest enrichment, sign-in activity"],
          ["Application.Read.All", "Application", "App registrations, credentials, owners, federated credentials"],
          ["RoleManagement.Read.Directory", "Application", "Role definitions, role assignments"],
          ["RoleManagement.Read.All", "Application", "PIM eligible + active schedule instances"],
          ["Policy.Read.All", "Application", "Conditional access policies, authorization policy, cross-tenant access"],
          ["GroupMember.Read.All", "Application", "Group membership, transitive members"],
        ]}
      />
      <SubHeading>Optional Permissions (License-Dependent)</SubHeading>
      <Table
        headers={["Permission", "License", "Purpose", "Impact if Missing"]}
        rows={[
          ["IdentityRiskEvent.Read.All", "Entra ID P2", "Risky users, risk detections", "Identity Protection signals skipped"],
          ["IdentityRiskyServicePrincipal.Read.All", "Workload ID Premium", "Risky service principals", "SP risk signals skipped"],
          ["AccessReview.Read.All", "Entra ID Governance", "Access review definitions", "Access review coverage analysis skipped"],
        ]}
      />
      <P>
        The application gracefully degrades when optional permissions or licenses are unavailable.
        A warning is logged for each skipped data source, and the corresponding analysis features
        are disabled without affecting the rest of the scan.
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
        <FeatureCard title="Identity Action Profiling" description="Ingests audit logs, sign-in logs, and activity logs. Builds per-identity action profiles for users, service principals, managed identities, and groups. Delta query support for incremental sync." badges={[{ label: "Core", color: "blue" }]} />
        <FeatureCard title="PIM-Aware Role Analysis" description="Fetches active and eligible PIM role assignments. Distinguishes direct, pim_eligible, pim_activated, and group assignment types. Tracks activation sessions." badges={[{ label: "Core", color: "blue" }, { label: "PIM", color: "purple" }]} />
        <FeatureCard title="Least-Privilege Recommender" description="Maps observed actions to required permissions using an 86-operation catalog. Recommends best-matching built-in roles (72 Entra + 57 Azure RBAC) or generates custom role definitions with reduction scoring." badges={[{ label: "Core", color: "blue" }]} />
        <FeatureCard title="Access Path Analysis" description="Detects indirect privilege escalation chains: app owner to SP, group owner to role, SP owner to permissions, and implicit app admin paths." badges={[{ label: "Advanced", color: "purple" }]} />
      </div>

      <SubHeading>Service Principal & Workload Identity</SubHeading>
      <div className="grid gap-3 sm:grid-cols-2">
        <FeatureCard title="SP Permission Usage Analysis" description="Cross-references SP's granted app permissions against actual API calls from sign-in logs. Identifies SPs with high-risk permissions they never use." badges={[{ label: "New", color: "green" }]} />
        <FeatureCard title="SP Credential Hygiene" description="Detects expired credentials, stale secrets (>365 days), multiple active credentials (>2), and unused credentials on service principals." badges={[{ label: "New", color: "green" }]} />
        <FeatureCard title="Managed Identity Analysis" description="Flags managed identities with admin roles (critical if Global Admin), broad root-scope assignments, or overprivileged configurations." badges={[{ label: "New", color: "green" }]} />
        <FeatureCard title="Federation Credential Validation" description="Checks federated identity credentials (GitHub Actions OIDC, Kubernetes) for wildcard subjects, overly broad issuer trusts, and missing audience restrictions." badges={[{ label: "New", color: "green" }]} />
      </div>

      <SubHeading>OAuth & Consent Governance</SubHeading>
      <div className="grid gap-3 sm:grid-cols-2">
        <FeatureCard title="Risky Consent Grant Detection" description="Identifies delegated grants for high-risk scopes (Mail.ReadWrite, Files.ReadWrite.All), grants to unverified publishers, and user-consented (vs admin-consented) high-privilege grants." badges={[{ label: "New", color: "green" }]} />
        <FeatureCard title="Consent Policy Analysis" description="Validates tenant-level consent settings: whether user consent is unrestricted to all apps and whether an admin consent workflow is configured." badges={[{ label: "New", color: "green" }]} />
      </div>

      <SubHeading>Identity Lifecycle</SubHeading>
      <div className="grid gap-3 sm:grid-cols-2">
        <FeatureCard title="Orphaned Account Detection" description="Flags disabled accounts that still hold active role assignments. Critical severity for disabled Global Administrators." badges={[{ label: "New", color: "green" }]} />
        <FeatureCard title="Offboarding Validation" description="Identifies recently disabled accounts (last seen within 30 days) that still have roles or group memberships, indicating incomplete offboarding." badges={[{ label: "New", color: "green" }]} />
        <FeatureCard title="Never-Used Account Detection" description="Flags accounts provisioned >30 days ago with no sign-in activity. Critical if the account holds admin roles — likely bulk provisioning or sync errors." badges={[{ label: "New", color: "green" }]} />
      </div>

      <SubHeading>Conditional Access & Policy</SubHeading>
      <div className="grid gap-3 sm:grid-cols-2">
        <FeatureCard title="12 CA Misconfiguration Checks" description="Legacy auth blocking, MFA gaps for admins and all users, admin exclusions, risk-based policies, device compliance, guest MFA, Azure Management portal, and more." badges={[{ label: "Core", color: "blue" }]} />
        <FeatureCard title="Group Membership Analysis" description="Ownerless role-assignable groups, non-RA groups with admin roles, dynamic groups with admin roles, broad membership rules, and large role-bearing groups." badges={[{ label: "Core", color: "blue" }]} />
        <FeatureCard title="Custom Role Governance" description="Wildcard permissions, escalation paths, >90% built-in overlap, unused roles, missing descriptions, and custom role sprawl (>20 custom roles)." badges={[{ label: "Core", color: "blue" }]} />
        <FeatureCard title="Access Review Coverage" description="Privileged roles without access reviews, role-assignable groups uncovered, stale reviews with no recurrence, and no guest-scoped review." badges={[{ label: "Core", color: "blue" }]} />
      </div>

      <SubHeading>Reporting & Remediation</SubHeading>
      <div className="grid gap-3 sm:grid-cols-2">
        <FeatureCard title="Executive Reports" description="Generate PDF and PowerPoint reports with risk scores, compliance metrics, top risky identities, and AI-generated narrative summaries." badges={[{ label: "Core", color: "blue" }]} />
        <FeatureCard title="IaC Export" description="Export role recommendations as Terraform HCL, Bicep, or ARM JSON templates. Supports bulk export as ZIP for up to 500 identities." badges={[{ label: "Core", color: "blue" }]} />
        <FeatureCard title="Remediation Workflow" description="Request, approve, reject, and execute remediation actions via the Graph API OBO flow. Immutable audit trail stored in Cosmos DB. Human confirmation required." badges={[{ label: "Core", color: "blue" }]} />
        <FeatureCard title="AI Narratives" description="GPT-4o-powered natural language summaries: executive digests, identity risk summaries, drift explanations, and recommendation rationale. 24-hour TTL caching." badges={[{ label: "AI", color: "amber" }]} />
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

      <SubHeading>Behavioral Detection Engine (7 Types)</SubHeading>
      <Table
        headers={["Detection", "Method", "Severity"]}
        rows={[
          ["First-Seen Action", "Flags any action not in the identity's 30-day baseline", "Medium"],
          ["Frequency Anomaly", "Z-score of daily action count vs rolling baseline stats", "z > 1.5 Low, > 2.0 Medium, > 3.0 High"],
          ["Time-of-Day Anomaly", "Flags actions at hours with <3 events in hour histogram and >2 stddev below mean", "Based on hour deviation"],
          ["Velocity / Burst", "Compares recent-hour action count to baseline hourly rate", "3x Medium, 5x High, 10x Critical"],
          ["Geo-Location Anomaly", "Sign-in from a country not in the identity's known locations", "High"],
          ["Impossible Travel", "Two sign-ins >500km apart within 1 hour (haversine great-circle distance)", "Critical"],
          ["Peer Group Deviation", "Z-score of action count vs role-based peer group (min 5 members)", "z > 2 Medium, > 3 High, > 4 Critical"],
        ]}
      />

      <SubHeading>Best Practice Rules (50+ Checks Across 11 Categories)</SubHeading>
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
          ["SP & Workload", "6", "SP overprivileged, unused permissions/credentials, MI overprivileged/broad, federation"],
          ["OAuth Consent", "5", "Risky consent, unverified publisher, user consent high-privilege, unrestricted"],
        ]}
      />

      <SubHeading>Risk Scoring</SubHeading>
      <P>
        Each identity receives a composite risk score (0-100) weighted across 6 components:
      </P>
      <Table
        headers={["Component", "Weight", "Signal"]}
        rows={[
          ["Drift Alerts", "20%", "Open drift alerts count and severity"],
          ["Overprivilege", "20%", "Ratio of unused vs granted permissions"],
          ["Admin Roles", "15%", "Permanent admin roles without PIM"],
          ["Stale Access", "15%", "Days since last sign-in activity"],
          ["Identity Protection", "20%", "Entra ID risk level (atRisk, confirmedCompromised)"],
          ["Guest / B2B Risk", "10%", "Guest type, MFA status, admin roles"],
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
        which controls pass or fail based on active violations in your tenant.
      </P>
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { name: "CIS Microsoft 365", version: "Foundations Benchmark v3.1.0", count: 23, color: "text-blue-600 dark:text-blue-400", sections: "Identity, Privileged Access, Guest Access, Applications, Governance, Conditional Access, Roles" },
          { name: "NIST SP 800-53", version: "Rev. 5", count: 22, color: "text-emerald-600 dark:text-emerald-400", sections: "Access Control, Identification/Auth, Config Management, Risk Assessment, Personnel Security" },
          { name: "SOC 2 Type II", version: "Trust Services Criteria 2017", count: 14, color: "text-purple-600 dark:text-purple-400", sections: "Common Criteria (CC6-CC8), Availability, Confidentiality" },
        ].map((fw) => (
          <div key={fw.name} className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800/50">
            <div className="text-sm font-semibold text-slate-900 dark:text-white">{fw.name}</div>
            <div className="text-xs text-slate-500 dark:text-slate-400">{fw.version}</div>
            <div className={clsx("mt-2 text-2xl font-bold", fw.color)}>{fw.count}</div>
            <div className="text-xs text-slate-400">controls mapped</div>
            <div className="mt-2 text-[10px] leading-relaxed text-slate-400">{fw.sections}</div>
          </div>
        ))}
      </div>
      <SubHeading>How It Works</SubHeading>
      <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 dark:border-slate-700 dark:bg-slate-800/30">
        <ol className="ml-4 list-decimal space-y-1 text-sm text-slate-600 dark:text-slate-400">
          <li>Each <Code>ViolationType</Code> maps to one or more framework control IDs via JSON mapping files.</li>
          <li>The compliance mapper loads all framework definitions at startup.</li>
          <li>For a given set of violations, each control is marked pass (no matching violations) or fail (one or more).</li>
          <li>A per-framework score is computed: <Code>(passed / total) * 100%</Code>.</li>
          <li>Failed controls include linked violation IDs for drill-down.</li>
        </ol>
      </div>
      <P>
        Use the <strong>Reports</strong> page to generate per-framework compliance evidence reports in PDF format,
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
        and <Code>/redoc</Code> (ReDoc) on the backend server.
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
          ["GET", "/identities", "Paginated, filterable identity list (type, risk, search)"],
          ["GET", "/identities/{id}", "Identity detail with PIM roles, risk, group memberships"],
          ["GET", "/identities/{id}/actions", "Action history timeline with pagination"],
        ]}
      />

      <SubHeading>Recommendations & Exports</SubHeading>
      <Table
        headers={["Method", "Endpoint", "Description"]}
        rows={[
          ["GET", "/recommendations", "Paginated recommendation list with reduction scores"],
          ["GET", "/recommendations/{id}", "Recommendation detail per identity with role diff"],
          ["POST", "/recommendations/compute", "Trigger batch computation (202 Accepted)"],
          ["GET", "/exports/{id}?format=terraform|bicep|arm", "Export IaC for an identity"],
          ["POST", "/exports/bulk", "Bulk export (max 500 identities, returns ZIP)"],
        ]}
      />

      <SubHeading>Drift Detection</SubHeading>
      <Table
        headers={["Method", "Endpoint", "Description"]}
        rows={[
          ["GET", "/drift-alerts", "Filterable drift alert list (severity, status, type)"],
          ["GET", "/drift-alerts/{id}", "Alert detail with evidence and z-score"],
          ["PATCH", "/drift-alerts/{id}", "Update status (acknowledge / escalate / resolve)"],
          ["POST", "/drift-alerts/detect", "Trigger on-demand detection (202 Accepted)"],
          ["GET", "/baselines/{id}", "View baseline statistics for an identity"],
        ]}
      />

      <SubHeading>Best Practices & Compliance</SubHeading>
      <Table
        headers={["Method", "Endpoint", "Description"]}
        rows={[
          ["GET", "/best-practices", "Filterable violation list (50+ types, priority, category)"],
          ["GET", "/best-practices/summary", "Aggregated compliance score"],
          ["GET", "/best-practices/{id}", "Violation detail with remediation steps"],
          ["POST", "/best-practices/evaluate", "Trigger full evaluation (202 Accepted)"],
        ]}
      />

      <SubHeading>Remediation</SubHeading>
      <Table
        headers={["Method", "Endpoint", "Description"]}
        rows={[
          ["GET", "/remediation", "Paginated remediation action history"],
          ["POST", "/remediation/request", "Request a new remediation action"],
          ["POST", "/remediation/{id}/approve", "Approve a pending action"],
          ["POST", "/remediation/{id}/reject", "Reject a pending action"],
        ]}
      />

      <SubHeading>Reports & Narratives</SubHeading>
      <Table
        headers={["Method", "Endpoint", "Description"]}
        rows={[
          ["GET", "/reports/executive?format=pdf|pptx", "Download executive report"],
          ["GET", "/reports/compliance?framework=cis_m365|nist_800_53|soc2", "Compliance evidence report"],
          ["GET", "/narratives/executive", "AI-generated executive digest"],
          ["POST", "/narratives/refresh", "Force regenerate AI narratives"],
        ]}
      />

      <SubHeading>Scan & Settings</SubHeading>
      <Table
        headers={["Method", "Endpoint", "Description"]}
        rows={[
          ["POST", "/sync/trigger?full=false", "Trigger Graph API data sync"],
          ["GET", "/sync/status", "Current sync state"],
          ["GET", "/settings", "Project configuration"],
          ["GET", "/settings/sod-rules", "List SoD conflict rules"],
          ["POST", "/settings/sod-rules", "Create custom SoD rule"],
          ["GET", "/settings/scan-schedules", "List scan schedules"],
          ["POST", "/settings/scan-schedules", "Create scan schedule (cron expression)"],
          ["GET", "/settings/alert-rules", "List alert rules"],
          ["POST", "/settings/alert-rules", "Create alert rule (email/Teams/webhook)"],
        ]}
      />

      <SubHeading>System Endpoints (No Auth Required)</SubHeading>
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
        Users are assigned roles through the Entra ID app registration enterprise application.
      </P>
      <Table
        headers={["Role", "Access Scope", "Typical User"]}
        rows={[
          ["SecurityEngineer", "Drift alerts, identity deep-dive, action timeline, baselines, PIM sessions, access paths", "SOC analyst, security operations"],
          ["IAMAdmin", "Recommendations, IaC exports, best practices, settings, scan triggers, remediation, alert rules, SoD rules", "IAM team lead, identity admin"],
          ["Executive", "Dashboard, summary views, reports, AI narratives, analytics", "CISO, VP of Security, compliance officer"],
        ]}
      />
      <SubHeading>Project-Level Roles</SubHeading>
      <Table
        headers={["Role", "Permissions", "Who"]}
        rows={[
          ["Admin", "Full project access, manage members, delete project", "Project owner (automatic), promoted members"],
          ["Operator", "Run scans, trigger evaluations, view all data", "IAM engineers, security analysts"],
          ["Viewer", "Read-only access to all project data", "Auditors, compliance reviewers"],
        ]}
      />
      <P>
        The project owner is implicitly an admin. Project access is validated on every
        API request — users can only access projects they are members of. Cross-tenant
        data access is structurally impossible at the data layer (Cosmos DB partition key).
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
          ["BACKEND_PORT", "No", "8000", "Server listen port"],
          ["AZURE_CLIENT_ID", "Prod", "", "Entra ID application client ID"],
          ["AZURE_CLIENT_SECRET", "Prod", "", "Entra ID client secret"],
          ["AZURE_TENANT_ID", "Prod", "", "Entra ID tenant ID (for OBO flow)"],
          ["COSMOS_ENDPOINT", "Prod", "https://localhost:8081", "Cosmos DB account endpoint"],
          ["COSMOS_KEY", "Prod", "", "Cosmos DB access key"],
          ["COSMOS_MASTER_DATABASE", "No", "entra-master", "Master database name"],
          ["REDIS_HOST", "No", "localhost", "Redis hostname"],
          ["REDIS_PORT", "No", "6379", "Redis port"],
          ["REDIS_PASSWORD", "Prod", "", "Redis password"],
          ["REDIS_SSL", "No", "false", "Enable TLS for Redis"],
          ["KEYVAULT_URL", "Prod", "", "Azure Key Vault URL"],
          ["AZURE_FOUNDRY_ENDPOINT", "No", "", "Azure AI Foundry endpoint"],
          ["AZURE_FOUNDRY_KEY", "No", "", "Azure AI Foundry API key"],
          ["AZURE_FOUNDRY_MODEL", "No", "gpt-4o", "AI model deployment name"],
          ["GRAPH_API_VERSION", "No", "beta", "Graph API version (beta or v1.0)"],
          ["CORS_ORIGINS", "No", "http://localhost:5173", "Comma-separated allowed origins"],
          ["ENCRYPTION_KEY", "Prod", "", "Base64-encoded 32-byte AES-256-GCM key for credential encryption"],
          ["PIM_SESSION_ENABLED", "No", "true", "Enable PIM privileged session tracking"],
          ["APPLICATIONINSIGHTS_CONNECTION_STRING", "No", "", "Application Insights connection string"],
        ]}
      />
      <SubHeading>Frontend Environment Variables</SubHeading>
      <Table
        headers={["Variable", "Required", "Default", "Description"]}
        rows={[
          ["VITE_APP_CLIENT_ID", "Prod", "", "Entra ID application client ID"],
          ["VITE_TENANT_ID", "Prod", "common", "Entra ID tenant for MSAL authority"],
          ["VITE_API_BASE_URL", "No", "", "API override (empty = same-origin /api/* proxy)"],
          ["VITE_LOCAL_MODE", "No", "false", "Skip MSAL authentication (dev only)"],
        ]}
      />
      <SubHeading>Security Notes</SubHeading>
      <div className="rounded-xl border border-red-200 bg-red-50/50 p-4 dark:border-red-800 dark:bg-red-900/20">
        <ul className="ml-4 list-disc space-y-1 text-sm text-slate-700 dark:text-slate-300">
          <li><Code>LOCAL_MODE</Code> must <strong>never</strong> be enabled in staging or production.</li>
          <li>All secrets (<Code>COSMOS_KEY</Code>, <Code>REDIS_PASSWORD</Code>, <Code>AZURE_FOUNDRY_KEY</Code>, <Code>AZURE_CLIENT_SECRET</Code>, <Code>ENCRYPTION_KEY</Code>) must be stored in Azure Key Vault in production — never in environment variables or code.</li>
          <li>The application uses managed identity for service-to-service communication — never connection strings.</li>
          <li>Redis TLS is enforced in production (non-SSL port disabled).</li>
        </ul>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Search component
// ---------------------------------------------------------------------------

function SearchBar({
  query,
  onChange,
  onClear,
  resultCount,
  onResultClick,
  results,
}: {
  query: string;
  onChange: (q: string) => void;
  onClear: () => void;
  resultCount: number;
  onResultClick: (id: SectionId) => void;
  results: SearchEntry[];
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === "Escape") {
        onClear();
        inputRef.current?.blur();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClear]);

  return (
    <div className="relative">
      <div className="relative">
        <svg className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          ref={inputRef}
          type="text"
          placeholder="Search documentation... (Ctrl+K)"
          value={query}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-20 text-sm text-slate-800 placeholder-slate-400 shadow-sm outline-none transition-all focus:border-brand-400 focus:ring-2 focus:ring-brand-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:placeholder-slate-500 dark:focus:border-brand-500 dark:focus:ring-brand-900/30"
        />
        {query && (
          <div className="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-2">
            <span className="text-xs text-slate-400">{resultCount} result{resultCount !== 1 ? "s" : ""}</span>
            <button type="button" onClick={onClear} aria-label="Clear search" className="rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-300">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}
      </div>
      {query && results.length > 0 && (
        <div className="absolute left-0 right-0 z-10 mt-1 rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
          {results.map((r) => (
            <button
              type="button"
              key={r.section}
              onClick={() => onResultClick(r.section)}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors first:rounded-t-xl last:rounded-b-xl hover:bg-slate-50 dark:hover:bg-slate-700/50"
            >
              <svg className="h-4 w-4 shrink-0 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <div>
                <div className="text-sm font-medium text-slate-800 dark:text-slate-200">{r.title}</div>
                <div className="text-xs text-slate-400 dark:text-slate-500">
                  {r.text.slice(0, 80)}...
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page — public, standalone layout
// ---------------------------------------------------------------------------

export function DocsPage() {
  const [activeSection, setActiveSection] = useState<SectionId>("overview");
  const [searchQuery, setSearchQuery] = useState("");
  const mainRef = useRef<HTMLElement>(null);

  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const terms = searchQuery.toLowerCase().split(/\s+/).filter(Boolean);
    return SEARCH_INDEX.filter((entry) => {
      const haystack = (entry.title + " " + entry.text).toLowerCase();
      return terms.every((term) => haystack.includes(term));
    });
  }, [searchQuery]);

  const matchedSections = useMemo(
    () => new Set(searchResults.map((r) => r.section)),
    [searchResults],
  );

  const scrollToSection = useCallback((id: SectionId) => {
    setActiveSection(id);
    setSearchQuery("");
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const isFiltered = searchQuery.trim().length > 0;

  return (
    <div className="flex h-screen flex-col bg-slate-50 dark:bg-slate-950">
      {/* Top header */}
      <header className="flex shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-700 dark:bg-slate-900">
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 shadow-sm"
          >
            <svg className="h-4.5 w-4.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </Link>
          <div>
            <h1 className="text-base font-bold tracking-tight text-slate-900 dark:text-white">
              Entra Permissions Analyzer
            </h1>
            <p className="text-[11px] font-medium text-slate-400 dark:text-slate-500">Documentation</p>
          </div>
        </div>
        <div className="w-full max-w-md">
          <SearchBar
            query={searchQuery}
            onChange={setSearchQuery}
            onClear={() => setSearchQuery("")}
            resultCount={searchResults.length}
            onResultClick={scrollToSection}
            results={searchResults}
          />
        </div>
        <Link
          to="/"
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
        >
          Go to App
        </Link>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* Sticky sidebar TOC */}
        <nav className="hidden w-56 shrink-0 overflow-y-auto border-r border-slate-200 bg-white px-3 py-6 dark:border-slate-700 dark:bg-slate-900 lg:block">
          <p className="mb-3 px-2 text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
            On This Page
          </p>
          <ul className="space-y-0.5">
            {TOC.map((item) => {
              const dimmed = isFiltered && !matchedSections.has(item.id);
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => scrollToSection(item.id)}
                    className={clsx(
                      "w-full rounded-lg px-2 py-1.5 text-left text-xs font-medium transition-colors",
                      dimmed && "opacity-30",
                      activeSection === item.id
                        ? "bg-brand-50 text-brand-700 dark:bg-brand-950/50 dark:text-brand-300"
                        : "text-slate-500 hover:bg-slate-50 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-300",
                    )}
                  >
                    {item.label}
                    {isFiltered && matchedSections.has(item.id) && (
                      <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-brand-500" />
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Main content */}
        <main
          ref={mainRef}
          className="flex-1 overflow-y-auto px-6 py-6 lg:px-10"
          onScroll={(e) => {
            if (isFiltered) return;
            const container = e.currentTarget;
            for (const item of [...TOC].reverse()) {
              const el = document.getElementById(item.id);
              if (el && el.offsetTop - container.scrollTop <= 120) {
                setActiveSection(item.id);
                break;
              }
            }
          }}
        >
          <div className="mx-auto max-w-4xl space-y-10">
            {(!isFiltered || matchedSections.has("overview")) && <OverviewSection />}
            {(!isFiltered || matchedSections.has("getting-started")) && <GettingStartedSection />}
            {(!isFiltered || matchedSections.has("prerequisites")) && <PrerequisitesSection />}
            {(!isFiltered || matchedSections.has("permissions")) && <PermissionsSection />}
            {(!isFiltered || matchedSections.has("features")) && <FeaturesSection />}
            {(!isFiltered || matchedSections.has("detections")) && <DetectionsSection />}
            {(!isFiltered || matchedSections.has("compliance")) && <ComplianceSection />}
            {(!isFiltered || matchedSections.has("api")) && <ApiSection />}
            {(!isFiltered || matchedSections.has("roles")) && <RolesSection />}
            {(!isFiltered || matchedSections.has("configuration")) && <ConfigurationSection />}

            {isFiltered && matchedSections.size === 0 && (
              <div className="py-20 text-center">
                <svg className="mx-auto h-12 w-12 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <p className="mt-3 text-sm font-medium text-slate-500 dark:text-slate-400">
                  No results for "{searchQuery}"
                </p>
                <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                  Try different keywords or clear the search
                </p>
              </div>
            )}

            <div className="border-t border-slate-200 pt-6 dark:border-slate-700">
              <p className="text-xs text-slate-400 dark:text-slate-500">
                Entra Permissions Analyzer v0.8.0 &middot; Powered by Microsoft Entra ID &middot; Built with FastAPI + React
              </p>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
