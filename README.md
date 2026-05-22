# Entra Permissions Analyzer

A multi-tenant SaaS application that connects to Microsoft Entra ID tenants via Microsoft Graph API, analyzes audit/sign-in/activity logs to build per-identity action profiles, recommends least-privilege roles, detects permission drift in near-real-time, evaluates 30+ best-practice rules across identities, apps, groups, and policies, and presents everything in a persona-aware executive dashboard with AI-generated narratives and compliance evidence export.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Data Model](#data-model)
- [Security](#security)
- [Infrastructure](#infrastructure)
- [CI/CD](#cicd)
- [Testing](#testing)

---

## Features

### Identity Action Profiling
- Ingests Entra ID audit logs, sign-in logs, and Azure activity logs via Microsoft Graph API
- Builds per-identity action profiles (users, service principals, managed identities, groups)
- Enriches profiles with UPN, app_id, user_type, and external user state from Graph user/SP lookups
- Delta query support for incremental sync with configurable schedule (default: every 6 hours)
- Full action timeline with resource context and result status

### PIM-Aware Role Analysis
- Fetches active and eligible role assignments via GA v1.0 PIM schedule instance APIs (`roleAssignmentScheduleInstances`, `roleEligibilityScheduleInstances`)
- Distinguishes assignment types: `direct`, `pim_eligible`, `pim_activated`, `group`
- Computes `is_permanent` from real data (not hardcoded) based on `assignmentType` and `endDateTime`
- Falls back to legacy `roleAssignments` endpoint when PIM APIs return 403 (missing `RoleManagement.Read.All`)
- Recognizes PIM audit events (activation, deactivation, eligibility changes) in the ingest pipeline

### Least-Privilege Role Recommender
- Maps observed actions to required Microsoft Graph API permissions using an 86-operation catalog
- Compares current role assignments against minimum required permissions
- Identifies excessive privileges with side-by-side permission delta view
- Recommends best-matching built-in roles (72 Entra ID + 57 Azure RBAC) with coverage scoring
- Generates custom role definitions when no built-in role fits
- Computes a reduction score showing how much privilege can be removed
- Exports recommendations to **Terraform HCL**, **Bicep**, and **ARM JSON** templates

### Permission Drift Detection
- **Multi-layer detection engine:**
  - **First-seen detection** — flags any action not previously observed in an identity's baseline
  - **Z-score anomaly detection** — rolling statistics (mean, stddev) per identity per action; z > 3.0 = High, z > 2.0 = Medium, z > 1.5 = Low severity
  - **Time-of-day anomaly** — hour-of-day histogram per identity; flags actions outside normal working hours (>2 stddev from hour distribution)
  - **Velocity / burst detection** — compares recent-hour action count to baseline hourly rate; 3x = Medium, 5x = High, 10x = Critical
  - **Geo-location anomaly** — sign-in from a country not in the identity's known location profile
  - **Impossible travel** — two sign-ins >500km apart within 1 hour (haversine distance calculation)
  - **Peer group deviation** — z-score of action count vs role-based peer group mean; z > 2 = Medium, z > 3 = High, z > 4 = Critical
- **Identity Protection integration** — auto-creates drift alerts when Entra ID flags an identity as `atRisk` or `confirmedCompromised`
- Rolling 30-day baselines computed daily with hour-of-day histograms and hourly rate statistics
- Identities with < 7 days of baseline data use first-seen only
- Drift alert workflow: Open, Acknowledged, Escalated, Resolved
- Composite risk scoring (0-100) weighted across 6 components: drift alerts (20%), overprivilege (20%), admin roles (15%), stale access (15%), identity protection (20%), guest/B2B risk (10%)

### Best Practice Advisor
Rule engine evaluating identities, apps, groups, and policies against 50+ Entra ID and Azure RBAC best practices:

#### Identity Rules

| Rule | What It Checks | Priority |
|------|---------------|----------|
| Stale Identity | No sign-in activity in 30/60/90 days | Medium / High / Critical |
| Permanent Admin | Admin roles without time-bound assignment | Critical / High |
| No PIM | Privileged roles not managed via PIM (checks eligible_roles) | High |
| Overprivileged | More permissions assigned than observed in use | Medium |
| Separation of Duties | Single identity holding conflicting admin roles (20 configurable pairs) | Critical / High / Medium |
| Role-Assignable Group | Groups that can be assigned directory roles | Medium |

#### App Registration Rules

| Rule | What It Checks | Priority |
|------|---------------|----------|
| Credential Expiry | Expired, expiring (<30d/<90d), or age >365d credentials | Critical / High / Medium |
| No Owner | App registration with zero owners | High |
| Multi-Tenant + High Privilege | Multi-tenant app with dangerous permissions | Critical / High |
| Excessive Permissions | >10 app permissions or requests Directory.ReadWrite.All / RoleManagement.ReadWrite.Directory | Critical / High |

#### MFA Rules

| Rule | What It Checks | Priority |
|------|---------------|----------|
| No MFA Registered | Identity has no MFA method registered | Critical (admins) / High (users) |
| Weak MFA Only | Only SMS or email as MFA method | High |
| Admin No Phishing-Resistant | Admin without FIDO2/WHfB/certificate-based auth | High |

#### Guest / B2B Rules

| Rule | What It Checks | Priority |
|------|---------------|----------|
| Guest Admin | Guest user with admin roles | Critical |
| Stale Guest | Guest with no sign-in >90 days | High |
| Pending Invitation | Guest invitation pending >30 days | Medium |
| Guest No MFA | Guest without MFA registration | Medium |

#### Conditional Access Policy Rules (12 checks)

| Rule | What It Checks | Priority |
|------|---------------|----------|
| Legacy Auth Not Blocked | No policy blocking Exchange ActiveSync + other legacy clients | Critical |
| No MFA for Admins | No MFA policy targeting admin role template IDs | Critical |
| Admin Excluded from MFA | Admin role IDs in MFA policy exclusions | Critical |
| No MFA for All Users | No MFA policy covering all users and all apps | High |
| Excessive Exclusions | MFA policy with >5 excluded users/groups | High |
| No Risk-Based Policy | No policy using signInRiskLevels or userRiskLevels | High |
| No Guest MFA | No policy targeting GuestsOrExternalUsers with MFA | High |
| No Azure Management MFA | No MFA policy for Azure Management portal | High |
| Report-Only Critical | Legacy-auth-block or all-users-MFA policy in report-only mode | Medium |
| No Device Compliance | No policy requiring compliant or domain-joined device | Medium |
| Grant Controls OR | Policy with OR operator for multiple grant controls | Medium |
| All-Apps Exclusions | Policy covering all apps but excluding specific apps | Medium |

#### Group Analysis Rules

| Rule | What It Checks | Priority |
|------|---------------|----------|
| Ownerless Role-Assignable Group | Role-assignable group with zero owners | High |
| Non-Role-Assignable Admin Group | Group with admin roles that isn't role-assignable | High |
| Dynamic Group Admin Roles | Dynamic membership group assigned admin roles | Medium |
| Broad Dynamic Rule | Dynamic group with overly permissive membership rule | Medium |
| Large Role-Assignable Group | Role-assignable group with >50 members | Medium |

#### Custom Role Rules

| Rule | What It Checks | Priority |
|------|---------------|----------|
| Wildcard Permissions | Custom role using `*/allTasks` wildcards | Critical |
| Escalation Paths | Custom role with credential update or role assignment permissions | Critical |
| >90% Built-in Overlap | Custom role that duplicates a built-in role | Medium |
| Unused Role | Custom role with zero assignments | Low |
| No Description | Custom role missing a description | Low |
| Custom Role Sprawl | Tenant has >20 custom roles | Medium |

#### Access Review Coverage

| Rule | What It Checks | Priority |
|------|---------------|----------|
| Privileged Roles Uncovered | Admin roles without a configured access review | High |
| Role-Assignable Groups Uncovered | Role-assignable groups without access review | Medium |
| Stale Reviews | Access reviews with no recurrence and last instance >6 months ago | Medium |
| No Guest Review | No access review scoped to guest members | High |

#### Identity Lifecycle Rules

| Rule | What It Checks | Priority |
|------|---------------|----------|
| Orphaned Account | Disabled account still holding active role assignments | Critical (admin) / High |
| Incomplete Offboarding | Recently disabled account with remaining roles or group memberships | High |
| Never-Used Account | Account created >30 days ago with no sign-in activity | Critical (admin) / Medium |

#### Service Principal & Workload Identity Rules

| Rule | What It Checks | Priority |
|------|---------------|----------|
| SP Overprivileged | SP with high-risk permissions never observed in use | Critical |
| SP Unused Permissions | SP with 3+ granted permissions never used | High |
| SP Unused Credential | SP credential with no sign-in activity | Medium |
| SP Multiple Active Credentials | SP with >2 active password credentials | Medium |
| MI Overprivileged | Managed identity with admin roles | Critical (GA) / High |
| MI Broad Scope | Managed identity with all roles at root scope | High |
| Federation Broad Subject | Federated credential with wildcard or empty subject filter | Critical / High |
| Federation No Audience | Federated credential with no audience restriction | Medium |

#### OAuth Consent Rules

| Rule | What It Checks | Priority |
|------|---------------|----------|
| Risky Consent Grant | Delegated grant for high-risk scopes (Mail.ReadWrite, Files.ReadWrite.All) | Critical / High |
| Unverified Publisher Consent | Consent grant to app from unverified publisher | High |
| User Consent High Privilege | User-consented (not admin-consented) high-privilege grant | High |
| User Consent Unrestricted | Tenant allows user consent to all apps | Critical |
| No Admin Consent Workflow | No admin consent workflow configured | Medium |

- Configurable Separation of Duties policy engine with 20 built-in conflict pairs (expandable per-tenant via CRUD API)
- Compliance score (0-100%) with priority-weighted penalty deductions
- Actionable remediation steps for each violation
- Compliance framework mapping: CIS Microsoft 365 v3.1.0, NIST 800-53 Rev 5, SOC 2 Type II

### Remediation Workflow
- Request/approve/reject/execute lifecycle for remediation actions
- Action types: remove role, create PIM eligible assignment, disable account, remove group member, revoke consent, remove app credential, convert permanent to PIM
- All write operations use delegated OBO flow (never app-only permissions)
- Immutable audit trail in Cosmos DB
- Human confirmation required before execution

### Conditional Access Analysis
- Fetches all CA policies via `Policy.Read.All`
- 12 misconfiguration checks covering legacy auth, MFA gaps, exclusion abuse, risk-based policies, device compliance, and Azure Management portal protection
- Tenant-level violations (not per-identity)

### Group Membership Analysis
- Fetches groups with `ConsistencyLevel: eventual` header for advanced queries
- Transitive member enumeration for role-assignable groups
- Dynamic group rule audit for overly broad membership criteria
- Hidden privilege escalation detection via nested group chains

### Identity Protection Integration
- Ingests risky user signals from Entra ID Protection (`riskyUsers`, `riskDetections`)
- Risk level mapping: high=100, medium=60, low=30 (amplified for `confirmedCompromised`)
- Auto-creates drift alerts for at-risk identities
- Graceful degradation when Entra ID P2 license is not available

### Custom Role Governance
- Inventories custom roles via `$filter=isBuiltIn eq false`
- Wildcard permission detection (`*/allTasks`)
- Built-in role overlap analysis (>90% = redundant)
- Escalation path detection (credential update + role assignment permissions)
- Unused role identification

### Scheduled Scanning & Alerting
- Cron-based scan scheduler with configurable schedules per project
- Outbound alert delivery via 3 channels:
  - **Email** — Microsoft Graph `sendMail` API
  - **Teams** — incoming webhook connector (MessageCard format)
  - **Webhook** — generic HTTP POST with HMAC-SHA256 signature
- Alert rule engine with severity filtering and condition-based triggers

### Executive Dashboard
- Tenant-wide risk score with color-coded gauge
- Summary cards: total identities, high-risk count, open drift alerts, compliance score
- 30-day trend charts for risk score, drift alerts, and identity count
- Top risky identities ranked by composite risk score
- AI-generated executive digest narratives via Microsoft Foundry

### AI Narrative Layer
- Natural language summaries powered by Azure AI Foundry (GPT-4o)
- Narrative types: executive digest, identity risk summary, drift explanation, recommendation rationale
- 24-hour TTL caching in Cosmos DB with stale-while-revalidate pattern
- Prompt injection sanitization on all identity-sourced data

### Compliance Evidence Export
- Maps 50+ violation types to three compliance frameworks via structured JSON mapping files:

| Framework | Version | Controls Mapped | Coverage |
|---|---|---|---|
| CIS Microsoft 365 | Foundations Benchmark v3.1.0 | 23 | Identity, privileged access, guest access, applications, governance, CA, roles |
| NIST SP 800-53 | Rev. 5 | 22 | Access control, identification/auth, config management, risk assessment, personnel security |
| SOC 2 Type II | Trust Services Criteria 2017 | 14 | Common criteria (CC6, CC7, CC8), availability, confidentiality |

- Compliance scoring engine computes per-framework pass/fail per control with linked violation IDs
- Per-framework compliance report generation with control coverage summary

### Real-Time Webhooks
- Microsoft Graph change notification subscriptions for near-real-time audit log updates
- Webhook validation handshake (validationToken echo as text/plain)
- `clientState` secret validation on incoming notifications
- Automatic processing through the same ingest pipeline as batch sync

### Report Export
- Executive reports in **PDF** (via reportlab) and **PowerPoint PPTX** (via python-pptx)
- Compliance evidence reports by framework (SOC 2, ISO 27001, NIST 800-53)
- Risk summary tables, compliance metrics, top risky identities
- JSON fallback when optional report libraries are not installed

### Persona-Aware Access Control
Three application roles with scoped access:

| Role | Access |
|------|--------|
| **SecurityEngineer** | Drift alerts, identity deep-dive, action timeline, baselines |
| **IAMAdmin** | Recommendations, IaC exports, best practices, settings, sync, onboarding, subscriptions, remediation |
| **Executive** | Dashboard, summary views, reports, AI narratives |

---

## Architecture

```
                    +---------------------------------------------------------+
                    |                    Azure Container Apps                  |
                    |  +--------------+              +----------------------+ |
  Users --MSAL------+  |   Frontend   |--REST API--->|      Backend         | |
  (Browser)         |  |  React + Vite |              |    FastAPI (Python)  | |
                    |  |   Tailwind    |              |                      | |
                    |  +--------------+              |  +------------------+| |
                    |                                |  |  Auth (JWT/OBO)  || |
                    |                                |  +------------------+| |
                    |                                |  |  15 Routers      || |
                    |                                |  |  (60+ endpoints) || |
                    |                                |  +------------------+| |
                    |                                |  |  30 Services     || |
                    |                                |  +------------------+| |
                    |                                |  |  4 Pipelines     || |
                    |                                |  +------------------+| |
                    |                                +----------+-----------+ |
                    |                                           |             |
                    |  +-------------------------------------+  |             |
                    |  |      5 Scheduled Jobs (CRON)        |  |             |
                    |  |  sync -> baselines -> drift -> recs |  |             |
                    |  |  -> narratives                      |  |             |
                    |  +-------------------------------------+  |             |
                    +-------------------------------------------+             |
                                           |                                 |
             +-----------------------------+-------------------------------- +
             |                             |
             v                             v
  +--------------------+       +----------------------+      +--------------+
  |  Azure Cosmos DB   |       |  Azure Cache for     |      |  Microsoft   |
  |  (NoSQL, Serverless)|      |  Redis               |      |  Graph API   |
  |                    |       |                      |      |              |
  |  18 containers     |       |  Dashboard cache     |      |  Audit logs  |
  |  Partition: /tenantId|     |  Rate limiting       |      |  Sign-ins    |
  +--------------------+       +----------------------+      |  PIM roles   |
                                                             |  CA policies |
                                                             |  Groups      |
                                                             |  Risk data   |
                                                             +--------------+
             +------------------+       +------------------+
             |  Azure Key Vault |       |  Azure AI Foundry |
             |  6 secrets       |       |  GPT-4o narratives |
             +------------------+       +------------------+
```

### Multi-Tenant Data Isolation

Every Cosmos DB container uses `/tenantId` (or `/projectId` for project-scoped containers) as the partition key. All repository methods require `tenant_id` as the first parameter, extracted from the authenticated user's JWT `tid` claim. Cross-tenant data access is structurally impossible at the data layer.

### Hybrid Sync Architecture

| Method | Trigger | Frequency | Mechanism |
|--------|---------|-----------|-----------|
| Batch sync | CRON job | Every 6 hours | Delta queries with stored delta links |
| Webhooks | Graph change notification | Near-real-time | Graph pushes audit events to `/api/webhooks/graph` |
| Scheduled scan | Configurable cron | Per-project | ScanScheduler checks due scans every 60 seconds |

### Scheduled Job Pipeline

Jobs run as Azure Container Apps Jobs in sequence:

| Job | Schedule | What It Does |
|-----|----------|-------------|
| `sync-tenant` | `0 */6 * * *` | Fetch new audit/sign-in logs, PIM roles, users, SPs, groups, CA policies, MFA data, risk detections |
| `compute-baselines` | `0 2 * * *` | Calculate 30-day rolling baseline statistics |
| `detect-drift` | `0 3 * * *` | Run first-seen + z-score anomaly detection |
| `generate-recommendations` | `0 4 * * *` | Compute least-privilege role recommendations |
| `generate-narratives` | `0 5 * * *` | Generate AI narrative digests via Foundry |

### Microsoft Graph API Permissions

#### Required

| Permission | Purpose |
|---|---|
| `AuditLog.Read.All` | Audit logs, sign-in logs, MFA registration reports |
| `Directory.Read.All` | Directory data, OAuth2 permission grants |
| `User.Read.All` | User profiles, guest enrichment |
| `Application.Read.All` | App registrations, credentials, owners |
| `RoleManagement.Read.Directory` | Role definitions, role assignments |
| `RoleManagement.Read.All` | PIM eligible + active schedule instances |
| `Policy.Read.All` | Conditional Access policies, cross-tenant access |
| `GroupMember.Read.All` | Group membership, transitive members |

#### Optional (license-dependent)

| Permission | License Required | Purpose |
|---|---|---|
| `IdentityRiskEvent.Read.All` | Entra ID P2 | Risky users, risk detections |
| `IdentityRiskyServicePrincipal.Read.All` | Workload ID Premium | Risky service principals |
| `AccessReview.Read.All` | Entra ID Governance | Access review definitions |

---

## Tech Stack

### Backend
| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.12 | Runtime |
| FastAPI | 0.115.12 | Web framework |
| Pydantic v2 | 2.11.3 | Data validation and models |
| azure-cosmos | 4.9.0 | Cosmos DB async SDK |
| azure-identity | 1.21.0 | Azure authentication |
| msal | 1.32.0 | Entra ID token handling (OBO flow) |
| PyJWT | 2.10.1 | JWT validation |
| redis | 5.2.1 | Async Redis client |
| httpx | 0.28.1 | Async HTTP client (Graph API, Foundry) |
| croniter | 2.0+ | Cron expression parsing for scan scheduler |
| OpenTelemetry | 1.33.0 | Distributed tracing |

### Frontend
| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 18.3 | UI framework |
| TypeScript | 5.6 | Type safety |
| Vite | 5.4 | Build tool and dev server |
| Tailwind CSS | 3.4 | Utility-first styling |
| @azure/msal-react | 2.1 | Entra ID authentication |
| @tanstack/react-query | 5.62 | Server state management |
| react-router-dom | 6.28 | Client-side routing |

### Infrastructure

### Deploying To An Existing Resource Group

The Terraform under [infra/envs/prod](c:\Users\jatmadan\Documents\GitHub\Entra-Permissions-Analyzer\infra\envs\prod) can now either create a new resource group and Entra app registration or reuse existing ones.

For the exact manual flow used for `rg-dmig`, run [scripts/deploy-existing-rg.ps1](c:\Users\jatmadan\Documents\GitHub\Entra-Permissions-Analyzer\scripts\deploy-existing-rg.ps1). It uses the checked-in Azure Blob backend in [infra/envs/prod/backend.tf](c:\Users\jatmadan\Documents\GitHub\Entra-Permissions-Analyzer\infra\envs\prod\backend.tf), provisions shared infrastructure, builds bootstrap images in ACR, applies the Container Apps resources, rebuilds the frontend against the live backend URL, and then runs smoke tests against the live frontend bundle. The script requires backend `/healthz` to pass, checks `/api/projects` based on the requested auth mode, and reports backend `/readyz` separately as a readiness gate with its response body if dependencies are not fully ready yet.

Run the script once with `-BootstrapAdoption` to import existing `rg-dmig` resources from Azure into the Azure Storage backend when the remote state is empty or missing addresses. After that first run, omit `-BootstrapAdoption` so normal deployments use remote state only and skip the repeated resource adoption path.

Example:

```powershell
./scripts/deploy-existing-rg.ps1 \
   -ResourceGroupName rg-dmig \
   -ExistingApplicationClientId 735e12ea-c482-4ccd-af90-8e36ecce1e9a \
   -ExistingApplicationClientSecret '<existing-app-secret>' \
   -FoundryEndpoint https://codex-jay-resource.openai.azure.com \
   -FoundryKey '<foundry-key>' \
   -GitHubRepository stark3998/Entra-Privilege-Analyzer \
   -BootstrapAdoption
```

Later runs should omit `-BootstrapAdoption`. Add `-SkipSmokeTests` if you need to stop after deployment without validating the live endpoints.

To deploy into an existing resource group such as `rg-dmig` and reuse an existing Entra app registration, provide these Terraform variables at plan/apply time:

- `existing_resource_group_name`
- `existing_application_client_id`
- `existing_application_client_secret`
- `foundry_endpoint`
- `foundry_key`
- `github_repository`

When reusing an existing app registration, that app must already expose the `access_as_user` scope, include the required redirect URIs for the deployed frontend URL, and have the Microsoft Graph permissions the backend expects.

The frontend image is build-time configured. For Azure deployments, pass `VITE_APP_CLIENT_ID`, `VITE_TENANT_ID`, and `BACKEND_URL` into the Docker build. Production traffic should use the frontend origin for `/api/*`, with nginx reverse proxying to the backend Container App so browser SSE stays same-origin. The GitHub frontend deployment workflow now expects these repo variables for this path:

- `APP_CLIENT_ID`
- `BACKEND_CONTAINER_APP_NAME`

| Technology | Purpose |
|-----------|---------|
| Azure Container Apps | Application hosting (backend, frontend, scheduled jobs) |
| Azure Cosmos DB | NoSQL database (serverless, 18 containers) |
| Azure Cache for Redis | Dashboard caching, rate limiting |
| Azure Key Vault | Secrets management (6 secrets) |
| Azure AI Foundry | AI narrative generation (GPT-4o) |
| Azure Container Registry | Container image storage |
| Application Insights | Observability and monitoring |
| Terraform | Infrastructure as Code |
| GitHub Actions | CI/CD pipelines |

---

## Project Structure

```
Entra-Permissions-Analyzer/
+-- .github/workflows/          # 5 CI/CD workflows
|   +-- ci.yml                  # Lint, test, type-check, security scan
|   +-- deploy-backend.yml      # Build and deploy backend Container App
|   +-- deploy-frontend.yml     # Build and deploy frontend Container App
|   +-- infra-plan.yml          # Terraform plan on PRs
|   +-- infra-apply.yml         # Terraform apply on merge
+-- backend/
|   +-- app/
|   |   +-- auth/               # JWT validation, OBO flow, role dependencies
|   |   |   +-- jwt.py          # Multi-tenant JWT validator (OIDC discovery, JWKS caching)
|   |   |   +-- deps.py         # CurrentUser, require_role(), validate_project_access()
|   |   |   +-- obo.py          # On-Behalf-Of token provider for Graph API
|   |   +-- data/               # Static catalogs and mappings
|   |   |   +-- permission_catalog.py   # Loads shared/permission_mappings.json
|   |   |   +-- builtin_roles.py        # Loads shared/builtin_roles_*.json
|   |   |   +-- compliance_mappings.py  # SOC 2, ISO 27001, NIST 800-53 control mappings
|   |   +-- models/             # 16 Pydantic v2 model files
|   |   |   +-- identity.py     # IdentityProfile with PIM, risk, group, guest fields
|   |   |   +-- action.py       # ActionEvent (audit log entry)
|   |   |   +-- role.py         # Role assignment and recommendation
|   |   |   +-- drift.py        # DriftAlert with identity protection types
|   |   |   +-- best_practice.py        # 50+ violation types
|   |   |   +-- app_registration.py     # App credentials, owners, permissions
|   |   |   +-- mfa_status.py           # MFA registration with method tier classification
|   |   |   +-- conditional_access.py   # CA policy conditions and grant controls
|   |   |   +-- group.py                # GroupProfile with membership analysis
|   |   |   +-- custom_role.py          # Custom role with overlap and escalation detection
|   |   |   +-- sod_policy.py           # 20 default SoD conflict pairs + custom rules
|   |   |   +-- access_review.py        # Access review definitions
|   |   |   +-- remediation.py          # Remediation workflow actions and statuses
|   |   |   +-- alert_rules.py          # Alert rules, channels, scan schedules
|   |   |   +-- project.py     # Project and membership models
|   |   |   +-- narrative.py   # Dashboard summary and AI narrative models
|   |   +-- pipelines/          # 4 pipeline orchestrators
|   |   +-- routers/            # 15 API router files (60+ endpoints)
|   |   +-- services/           # 22 service files
|   |   |   +-- cosmos.py               # CosmosRepo with 18 containers, 50+ methods
|   |   |   +-- graph_ingest.py         # 20+ Graph API fetch methods (PIM, CA, MFA, groups, risk)
|   |   |   +-- graph_roles.py          # PIM-aware role assignment fetching
|   |   |   +-- best_practice_analyzer.py  # 50+ rule checks + tenant-level analyzer orchestration
|   |   |   +-- ca_analyzer.py          # 12 Conditional Access misconfiguration checks
|   |   |   +-- group_analyzer.py       # Group membership and privilege analysis
|   |   |   +-- custom_role_analyzer.py # Custom role governance (6 checks)
|   |   |   +-- access_review_analyzer.py  # Access review coverage gaps (4 checks)
|   |   |   +-- risk_scorer.py          # 6-component composite risk scoring
|   |   |   +-- remediation_engine.py   # Request/approve/execute remediation workflow
|   |   |   +-- scheduler.py            # Cron-based scan scheduler
|   |   |   +-- alert_delivery.py       # Email, Teams, webhook alert delivery
|   |   |   +-- permission_validator.py # Graph API permission validation
|   |   |   +-- role_mapper.py          # Action-to-permission mapping
|   |   |   +-- role_recommender.py     # Least-privilege role recommendations
|   |   |   +-- drift_detector.py       # Multi-layer drift detection (first-seen, z-score, temporal, velocity)
|   |   |   +-- geo_analyzer.py        # Geo-location anomaly and impossible travel detection
|   |   |   +-- peer_group_analyzer.py # Role-based peer group behavioral deviation
|   |   |   +-- sp_permission_analyzer.py  # SP permission usage analysis (granted vs observed)
|   |   |   +-- consent_analyzer.py    # OAuth consent grant and tenant policy analysis
|   |   |   +-- managed_identity_analyzer.py  # Managed identity privilege analysis
|   |   |   +-- federation_analyzer.py # Workload identity federation credential validation
|   |   |   +-- compliance_mapper.py   # CIS/NIST/SOC2 compliance framework scoring engine
|   |   |   +-- narrative_engine.py     # AI narrative generation (Foundry)
|   |   |   +-- foundry.py             # FoundryClient wrapper
|   |   |   +-- report_generator.py    # PDF/PPTX report generation
|   |   |   +-- iac_exporter.py        # Terraform/Bicep/ARM export
|   |   |   +-- webhook.py            # Outbound webhook delivery
|   |   |   +-- crypto.py             # Credential encryption
|   |   +-- config.py           # pydantic-settings (18 configuration fields)
|   |   +-- main.py             # FastAPI app factory, middleware, lifespan
|   |   +-- observability.py    # OpenTelemetry + App Insights setup
|   +-- tests/                  # 7 test files, 104 test functions
|   +-- Dockerfile              # Multi-stage: dev (hot-reload) / prod (4 workers)
|   +-- pyproject.toml
+-- frontend/
|   +-- src/
|   |   +-- auth/               # MSAL config, useAuth hook, LoginGate
|   |   +-- api/
|   |   |   +-- types.ts        # 30+ TypeScript interfaces
|   |   |   +-- hooks.ts        # 30+ TanStack Query hooks
|   |   |   +-- projectHooks.ts # Project CRUD hooks
|   |   |   +-- client.ts       # Axios instance with auth interceptor
|   |   +-- components/         # 29+ React components across 7 categories
|   |   +-- pages/              # 16 page components
|   |   |   +-- DashboardPage.tsx
|   |   |   +-- AnalyticsPage.tsx
|   |   |   +-- IdentitiesPage.tsx / IdentityDetailPage.tsx
|   |   |   +-- RecommendationsPage.tsx / RecommendationDetailPage.tsx
|   |   |   +-- DriftPage.tsx / DriftDetailPage.tsx
|   |   |   +-- BestPracticesPage.tsx / BestPracticeDetailPage.tsx
|   |   |   +-- AppRegistrationsPage.tsx     # NEW: App credential hygiene
|   |   |   +-- ConditionalAccessPage.tsx    # NEW: CA policy analysis
|   |   |   +-- GroupsPage.tsx               # NEW: Group inventory
|   |   |   +-- CustomRolesPage.tsx          # NEW: Custom role governance
|   |   |   +-- RemediationHistoryPage.tsx   # NEW: Remediation audit trail
|   |   |   +-- ScanPage.tsx / ReportsPage.tsx / SettingsPage.tsx
|   |   +-- store/              # Project context provider
|   |   +-- App.tsx             # Route definitions
|   |   +-- main.tsx            # React DOM entry point
|   +-- Dockerfile
|   +-- package.json
|   +-- tailwind.config.ts
|   +-- vite.config.ts
+-- infra/                      # Terraform modules
+-- shared/                     # Static data files
|   +-- permission_mappings.json    # 72 Graph scopes, 86 audit operation mappings
|   +-- builtin_roles_entra.json   # 72 Entra ID built-in role definitions
|   +-- builtin_roles_azure.json   # 57 Azure RBAC built-in role definitions
|   +-- compliance_frameworks/     # Compliance framework control mappings
|       +-- cis_m365.json          # CIS Microsoft 365 v3.1.0 (23 controls)
|       +-- nist_800_53.json       # NIST SP 800-53 Rev 5 (22 controls)
|       +-- soc2.json              # SOC 2 Trust Services Criteria (14 controls)
+-- docker-compose.yml
+-- CLAUDE.md
```

---

## Getting Started

### Prerequisites

- **Python** 3.12+
- **Node.js** 20+
- **Docker** and **Docker Compose** (for local development)
- **Terraform** 1.5+ (for infrastructure deployment)
- An **Azure subscription** with permissions to create:
  - Entra ID app registrations
  - Cosmos DB accounts
  - Container Apps environments
  - Key Vault instances

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/stark3998/Entra-Privilege-Analyzer.git
   cd Entra-Permissions-Analyzer
   ```

2. **Copy environment file**
   ```bash
   cp .env.example .env
   ```

3. **Start with Docker Compose** (recommended)
   ```bash
   docker-compose up
   ```
   This starts the backend (port 8000), frontend (port 5173), and Redis (port 6379) in `LOCAL_MODE` with authentication disabled.

4. **Or start services individually**

   Backend:
   ```bash
   cd backend
   pip install -e ".[dev]"
   LOCAL_MODE=true uvicorn app.main:app --reload --port 8000
   ```

   Frontend:
   ```bash
   cd frontend
   npm install
   VITE_LOCAL_MODE=true npm run dev
   ```

5. **Verify**
   - Backend health: http://localhost:8000/healthz
   - Frontend: http://localhost:5173

### Production Deployment

See [Infrastructure](#infrastructure) for Terraform-based Azure deployment.

---

## Configuration

All environment variables are documented below per service. Copy `.env.example` to `.env` for local development — `deploy-local.ps1` auto-generates missing values like `ENCRYPTION_KEY`.

**Legend:** **Mandatory** = the service will not start or will critically malfunction without it. **Optional** = has a sensible default or enables a non-critical feature.

### Backend (FastAPI)

Defined in [config.py](backend/app/config.py). Loaded via Pydantic `BaseSettings` from env vars or `.env` file.

#### Core / App Mode

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `LOCAL_MODE` | No | `false` | `true`, `false` | Skip Entra ID auth and return a mock user. **Dev only — never enable in production.** |
| `DEBUG_MODE` | No | `false` | `true`, `false` | Detailed error responses with tracebacks, DEBUG-level logging |
| `BACKEND_PORT` | No | `8000` | Any valid port | Server listen port |
| `LOG_FORMAT` | No | `text` | `text`, `json` | `text` for local dev, `json` for production (structured logs for App Insights) |

#### Authentication (Entra ID)

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `AZURE_CLIENT_ID` | **Yes** (prod) | `""` | GUID | Entra ID application (client) ID for JWT validation and OBO flow |
| `AZURE_CLIENT_SECRET` | **Yes** (prod) | `""` | String | Entra ID client secret (stored in Key Vault in production) |
| `AZURE_TENANT_ID` | **Yes** (prod) | `""` | GUID | Entra ID tenant ID for the OBO flow authority |

#### CORS

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `CORS_ORIGINS` | No | `http://localhost:5173` | Comma-separated URLs | Explicit allowed origins for CORS |
| `CORS_ORIGIN_REGEX` | No | Container Apps pattern | Regex string | Regex pattern for dynamic origin matching (e.g., Azure Container Apps hostnames) |

#### Cosmos DB

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `COSMOS_ENDPOINT` | **Yes** | `https://localhost:8081` | URL | Cosmos DB account endpoint. Defaults to emulator for local dev |
| `COSMOS_KEY` | **Yes** | `""` | String | Cosmos DB access key. Use the [emulator well-known key](https://learn.microsoft.com/en-us/azure/cosmos-db/emulator) for local dev |
| `COSMOS_MASTER_DATABASE` | No | `entra-master` | String | Name of the master database for platform metadata |

#### Redis

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `REDIS_HOST` | No | `localhost` | Hostname | Redis server hostname |
| `REDIS_PORT` | No | `6379` | Port number | Redis server port |
| `REDIS_PASSWORD` | **Yes** (prod) | `""` | String | Redis password. Empty for local dev, required for Azure Cache for Redis |
| `REDIS_SSL` | No | `false` | `true`, `false` | Enable TLS for Redis. Must be `true` for Azure Cache for Redis |

#### Azure Key Vault

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `KEYVAULT_URL` | **Yes** (prod) | `""` | URL (`https://<name>.vault.azure.net`) | Key Vault URL for secret resolution at startup |

#### Microsoft Foundry (AI Narratives)

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `AZURE_FOUNDRY_ENDPOINT` | No | `""` | URL (`https://<name>.openai.azure.com`) | Azure AI Foundry endpoint. AI features are disabled when empty |
| `AZURE_FOUNDRY_KEY` | No | `""` | String | Azure AI Foundry API key (stored in Key Vault in production) |
| `AZURE_FOUNDRY_MODEL` | No | `gpt-4o` | Model deployment name | AI model deployment name for narrative generation |
| `AZURE_OPENAI_API_VERSION` | No | `2024-02-01` | API version string | Azure OpenAI API version |

#### Microsoft Graph

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `GRAPH_API_VERSION` | No | `beta` | `beta`, `v1.0` | Graph API version. `beta` for latest features (PIM, risk), `v1.0` for GA stability |

#### Scan Function App

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `SCAN_FUNCTION_APP_URL` | **Yes** (prod) | `""` | URL | Durable Functions scan orchestrator URL (e.g., `https://func-entraperm-scan-prod.azurewebsites.net`) |
| `SCAN_FUNCTION_KEY` | **Yes** (prod) | `""` | String | Function-level auth key for triggering scans (stored in Key Vault in production) |

#### Observability

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | No | `""` | Connection string | App Insights connection string. Enables distributed tracing and telemetry when set |
| `LOG_ANALYTICS_WORKSPACE_ID` | No | `""` | Azure resource ID | Log Analytics workspace resource ID. Enables the Function App Logs endpoint for KQL queries |
| `OTEL_SERVICE_NAME` | No | `entra-permissions-analyzer` | String | OpenTelemetry service name for traces |

#### Encryption

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `ENCRYPTION_KEY` | **Yes** (prod) | `""` | Base64-encoded 32-byte key | AES-256-GCM key for encrypting project client secrets at rest. `deploy-local.ps1` auto-generates one for local dev |

#### PIM Session Tracking

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `PIM_SESSION_ENABLED` | No | `true` | `true`, `false` | Enable PIM privileged session tracking |
| `PIM_SESSION_POLL_INTERVAL_MINUTES` | No | `15` | Integer | Polling interval for PIM session checks |
| `PIM_SESSION_BACKFILL_DAYS` | No | `30` | Integer | Number of days to backfill PIM session data |
| `PIM_SESSION_BUSINESS_HOURS_START` | No | `7` | 0-23 | Start of business hours (hour, 24h format) |
| `PIM_SESSION_BUSINESS_HOURS_END` | No | `19` | 0-23 | End of business hours (hour, 24h format) |

### Frontend (React + Vite)

Build-time variables prefixed with `VITE_` — baked into the JavaScript bundle at build. For Azure deployments, pass as Docker `--build-arg` values.

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `VITE_APP_CLIENT_ID` | **Yes** (prod) | `""` | GUID | Entra ID application client ID for MSAL authentication |
| `VITE_TENANT_ID` | No | `common` | GUID or `common` | Entra ID tenant for MSAL authority. `common` enables multi-tenant sign-in |
| `VITE_API_BASE_URL` | No | `""` | URL or empty | API base URL override. Leave empty for same-origin `/api/*` through the nginx reverse proxy (recommended for production) |
| `VITE_LOCAL_MODE` | No | `false` | `true`, `false` | Skip MSAL authentication. **Dev only — never enable in production.** |

#### Frontend Container (nginx, runtime)

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `BACKEND_URL` | No | `http://backend:8000` | URL | Backend origin for nginx reverse proxy (`/api/*` upstream). Set at Docker build time via `--build-arg` |

### Function App (Azure Durable Functions)

The Function App receives most configuration via the orchestration payload from the backend (Cosmos credentials, tenant credentials, etc.). Only a few env vars are set directly.

#### Azure Functions Runtime

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `AzureWebJobsStorage` | **Yes** | — | Connection string or `UseDevelopmentStorage=true` | Storage account for Durable Functions task hub (orchestration state, history) |
| `AzureWebJobsSecretStorageType` | No | `files` (local) | `files`, `blob` | Where the Functions host stores auth keys. `files` for local dev |
| `FUNCTIONS_WORKER_RUNTIME` | **Yes** | — | `python` | Must be `python` |
| `WEBSITE_HOSTNAME` | No | Auto-set by Azure | Hostname string | Functions host hostname. Set to `localhost:7071` in docker-compose |

#### Data Access

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `COSMOS_ENDPOINT` | **Yes** | — | URL | Cosmos DB endpoint. In production, uses Key Vault reference: `@Microsoft.KeyVault(SecretUri=...)` |
| `COSMOS_KEY` | **Yes** | — | String | Cosmos DB access key. In production, uses Key Vault reference |
| `COSMOS_DATABASE` | No | — | String | Cosmos DB database name (set by Terraform from `cosmos_database_name`) |
| `COSMOS_MASTER_DATABASE` | No | Same as `COSMOS_DATABASE` | String | Master database name for scan records |

#### Observability

| Variable | Mandatory | Default | Accepted Values | Description |
|----------|-----------|---------|-----------------|-------------|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | No | `""` | Connection string | Enables log forwarding to App Insights. Shared resource with the backend |

#### Local Dev Only (docker-compose)

These are set in `docker-compose.yml` for the Functions container but managed by the Azure platform in production:

| Variable | Mandatory | Default | Description |
|----------|-----------|---------|-------------|
| `REDIS_HOST` | No | `localhost` | Redis hostname (passed in orchestration payload in prod) |
| `REDIS_PORT` | No | `6379` | Redis port |
| `REDIS_PASSWORD` | No | `""` | Redis password |
| `REDIS_SSL` | No | `false` | Redis TLS |
| `ENCRYPTION_KEY` | No | `""` | Decryption key for project credentials |
| `LOCAL_MODE` | No | `false` | Skip auth in function triggers |

### Scheduled Jobs (Container App Jobs)

Jobs share the backend Docker image and receive the same env vars via Terraform. They use a subset of the backend configuration:

| Category | Variables Used |
|----------|---------------|
| **Cosmos DB** | `COSMOS_ENDPOINT`, `COSMOS_KEY`, `COSMOS_MASTER_DATABASE` |
| **Redis** | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_SSL` |
| **AI** | `AZURE_FOUNDRY_ENDPOINT`, `AZURE_FOUNDRY_KEY`, `AZURE_FOUNDRY_MODEL` |
| **Encryption** | `ENCRYPTION_KEY` |
| **Observability** | `APPLICATIONINSIGHTS_CONNECTION_STRING` |

Jobs do **not** receive: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, `KEYVAULT_URL`, `CORS_*`, `SCAN_FUNCTION_*`, `LOG_ANALYTICS_WORKSPACE_ID`.

### Production Secret Management

In production, sensitive values are stored in Azure Key Vault and injected as Container App secret references. The following env vars are **never** set as plain text in production:

| Env Var | Key Vault Secret Name | Container App Secret |
|---------|----------------------|---------------------|
| `COSMOS_KEY` | `cosmos-key` | `cosmos-key` |
| `COSMOS_ENDPOINT` | `cosmos-endpoint` | `cosmos-endpoint` |
| `REDIS_PASSWORD` | `redis-password` | `redis-password` |
| `AZURE_FOUNDRY_KEY` | `foundry-key` | `foundry-key` |
| `AZURE_CLIENT_SECRET` | `app-client-secret` | `app-client-secret` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `appinsights-conn-string` | `appinsights-connection-string` |
| `ENCRYPTION_KEY` | `encryption-key` | `encryption-key` |
| `SCAN_FUNCTION_KEY` | `scan-function-key` | `scan-function-key` |

The Function App uses Key Vault references (`@Microsoft.KeyVault(SecretUri=...)`) for `COSMOS_ENDPOINT`, `COSMOS_KEY`, and `APPLICATIONINSIGHTS_CONNECTION_STRING`.

---

## API Reference

### Project-Scoped API (`/api/projects/{project_id}/...`)

All project-scoped endpoints validate project membership and extract the target tenant ID automatically.

#### Dashboard & Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard` | Risk score, counts, compliance summary |
| GET | `/dashboard/trends` | 30-day time-series data |
| GET | `/analytics?days=30` | 14 analytics widgets (activity, permissions, security posture) |

#### Identities & Actions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/identities` | Paginated, filterable identity list |
| GET | `/identities/{iid}` | Identity detail with PIM roles, risk, group memberships |
| GET | `/identities/{iid}/actions` | Action history timeline |

#### Recommendations & Exports

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/recommendations` | Paginated recommendation list |
| GET | `/recommendations/{iid}` | Recommendation detail per identity |
| POST | `/recommendations/compute` | Trigger batch computation (202 Accepted) |
| GET | `/exports/{iid}?format=terraform\|bicep\|arm` | Export IaC for an identity |
| POST | `/exports/bulk` | Bulk export (max 500 identities, returns ZIP) |

#### Drift Detection

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/drift-alerts` | Filterable drift alert list |
| GET | `/drift-alerts/{aid}` | Alert detail with evidence |
| PATCH | `/drift-alerts/{aid}` | Update status (acknowledge/escalate/resolve) |
| POST | `/drift-alerts/detect` | Trigger on-demand detection (202 Accepted) |
| GET | `/baselines/{iid}` | View baseline statistics |

#### Best Practices

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/best-practices` | Filterable violation list (50+ types) |
| GET | `/best-practices/summary` | Aggregated compliance score |
| GET | `/best-practices/{vid}` | Violation detail with remediation steps |
| POST | `/best-practices/evaluate` | Trigger full evaluation (202 Accepted) |

#### App Registrations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/app-registrations` | Paginated app registration list with credential status |
| GET | `/app-registrations/{id}` | App registration detail |

#### Conditional Access

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/conditional-access` | CA policy list with analysis results |
| POST | `/conditional-access/analyze` | Trigger CA policy analysis (202 Accepted) |

#### Groups

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/groups` | Paginated group inventory |
| GET | `/groups/{id}` | Group detail with membership data |

#### Custom Roles

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/custom-roles` | Custom role inventory with governance analysis |

#### Access Reviews

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/access-reviews` | Access review definitions and coverage |

#### Remediation

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/remediation` | Paginated remediation action history |
| POST | `/remediation/request` | Request a new remediation action |
| POST | `/remediation/{id}/approve` | Approve a pending action |
| POST | `/remediation/{id}/reject` | Reject a pending action |

#### SoD Rules

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/settings/sod-rules` | List SoD conflict rules (built-in + custom) |
| POST | `/settings/sod-rules` | Create custom SoD rule |
| DELETE | `/settings/sod-rules/{id}` | Delete a custom SoD rule |

#### Scan Schedules

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/settings/scan-schedules` | List scan schedules for project |
| POST | `/settings/scan-schedules` | Create scan schedule (cron expression) |
| DELETE | `/settings/scan-schedules/{id}` | Delete scan schedule |

#### Alert Rules

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/settings/alert-rules` | List alert rules for project |
| POST | `/settings/alert-rules` | Create alert rule (email/Teams/webhook) |
| DELETE | `/settings/alert-rules/{id}` | Delete alert rule |

#### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/reports/executive?format=pdf\|pptx` | Download executive report |
| GET | `/reports/compliance?framework=cis_m365\|nist_800_53\|soc2` | Compliance evidence report |

#### Narratives

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/narratives/executive` | AI executive digest |
| POST | `/narratives/refresh` | Force regenerate narratives |

#### Sync & Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sync/trigger?full=false` | Trigger sync using project credentials |
| GET | `/sync/status` | Current sync state |
| GET | `/settings` | Project configuration |

### Legacy Tenant-Scoped API (`/api/tenants/{tid}/...`)

The original tenant-scoped endpoints remain available for backward compatibility.

### System Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/healthz` | Liveness probe |
| GET | `/readyz` | Readiness probe (checks Cosmos DB) |

**Total: 60+ endpoints across 15 routers.**

---

## Data Model

### Cosmos DB Containers

Containers use `/tenantId` or `/projectId` as partition keys for data isolation.

| Container | Partition Key | TTL | Contents |
|-----------|--------------|-----|----------|
| `tenant_configs` | `/tenantId` | None | Tenant settings (display name, sync schedule, baseline window) |
| `identity_profiles` | `/tenantId` | None | User/SP/MI/Group profiles with PIM roles, risk signals, group memberships |
| `action_events` | `/tenantId` | 90 days | Parsed audit log, sign-in log, and activity log events |
| `sync_state` | `/tenantId` | None | Delta links, timestamps, webhook subscription state |
| `role_recommendations` | `/tenantId` | None | Computed recommendations with built-in matches and custom roles |
| `drift_alerts` | `/tenantId` | None | Drift detection alerts with severity, status, and evidence |
| `baselines` | `/tenantId` | None | Rolling 30-day action frequency statistics (mean, stddev) |
| `best_practice_violations` | `/tenantId` | None | Best practice evaluation results with remediation steps |
| `narratives` | `/tenantId` | 24 hours | AI-generated narrative text |
| `projects` | `/ownerId` | None | Project definitions with encrypted credentials |
| `project_members` | `/projectId` | None | Project membership and role assignments |
| `scan_history` | `/projectId` | None | Scan execution records with phase tracking |
| `app_registrations` | `/tenantId` | None | App registration profiles with credential status |
| `mfa_records` | `/tenantId` | None | MFA registration status per user |
| `ca_policies` | `/tenantId` | None | Conditional Access policy snapshots |
| `risk_detections` | `/tenantId` | None | Identity Protection risk detections |
| `groups` | `/tenantId` | None | Group profiles with membership and role data |
| `access_reviews` | `/tenantId` | None | Access review definitions |
| `sod_rules` | `/tenantId` | None | Configurable SoD conflict pairs (built-in + custom) |
| `custom_roles` | `/tenantId` | None | Custom role profiles with governance analysis |
| `remediation_actions` | `/tenantId` | None | Remediation request/approval audit trail |
| `scan_schedules` | `/projectId` | None | Cron-based scan schedule configurations |
| `alert_rules` | `/projectId` | None | Alert rule configurations (email/Teams/webhook) |

### Key Pydantic Models

| Model | Key Fields |
|-------|-----------|
| `IdentityProfile` | identity_type, display_name, current_roles[], eligible_roles[], observed_actions[], risk_score, entra_risk_level, group_memberships[], user_type |
| `CurrentRole` | role_id, role_name, assignment_type (direct/pim_eligible/pim_activated/group), is_permanent, start_date, end_date |
| `ActionEvent` | action_name, resource_name, action_result, source (audit/sign-in/activity), timestamp |
| `RoleRecommendation` | current_roles, required_permissions, gaps[], best_builtin_match, alternatives[], custom_role, reduction_score |
| `DriftAlert` | drift_type (first_seen/frequency_anomaly/identity_protection), severity, status, z_score, entra_risk_level |
| `BestPracticeViolation` | violation_type (50+ types), priority, description, remediation_steps, affected_identity |
| `AppRegistrationProfile` | app_id, display_name, password_credentials[], key_credentials[], owner_count, high_risk_permissions[] |
| `ConditionalAccessPolicyRecord` | display_name, state, conditions, grant_controls |
| `GroupProfile` | display_name, is_role_assignable, is_dynamic, membership_rule, member_count, roles_assigned[] |
| `CustomRoleProfile` | display_name, permissions[], assignment_count, has_wildcard, has_escalation_paths |
| `SodConflictRule` | role_a_name, role_b_name, severity, rationale, is_custom, enabled |
| `RemediationAction` | action_type, target_identity_id, status (pending/approved/executing/completed/failed/rejected) |
| `MfaRegistrationRecord` | is_mfa_capable, is_mfa_registered, methods_registered[], strongest_method_tier |
| `ScanSchedule` | cron_expression, job_types[], enabled, last_run_at, next_run_at |
| `AlertRule` | rule_type, condition, channel (email/teams/webhook), severity_filter, enabled |

---

## Security

### Authentication & Authorization

- **Multi-tenant Entra ID**: MSAL with `common` authority accepts users from any Azure AD tenant
- **JWT validation**: Multi-tenant issuer validation (`https://login.microsoftonline.com/{tid}/v2.0`), RS256 signature verification, JWKS key caching with 1-hour rotation
- **On-Behalf-Of (OBO) flow**: Backend exchanges user tokens for Graph API tokens to call Microsoft Graph on behalf of the user's tenant
- **Role-based access control**: Three app roles (SecurityEngineer, IAMAdmin, Executive) enforced at every endpoint via `require_role()` dependency
- **Project access validation**: Every project-scoped endpoint verifies the user is an owner or member of the requested project
- **Remediation safety**: All Graph API write operations (role removal, account disable, etc.) use delegated OBO flow. The application never holds `RoleManagement.ReadWrite.Directory` as an application permission. Every remediation action requires human approval before execution.
- **LOCAL_MODE**: Single flag that bypasses all auth for development. Never enabled in staging or production.

### Data Protection

- **Tenant isolation**: Cosmos DB partition key `/tenantId` on all tenant-scoped containers ensures queries never cross tenant boundaries
- **Parameterized queries**: All Cosmos DB queries use `@param` binding -- no string interpolation of user values
- **Cosmos field stripping**: `ConfigDict(extra="ignore")` on all API-returned models prevents Cosmos metadata leakage (`_rid`, `_self`, `_etag`)
- **Credential encryption**: Project client secrets encrypted at rest via `CryptoService` before storage in Cosmos DB
- **Secrets management**: All sensitive values (Cosmos key, Redis password, Foundry key, client secret, App Insights connection string) stored in Azure Key Vault -- never in environment variables or code

### Input Validation & Sanitization

- **IaC template injection prevention**: `_sanitize_hcl()` and `_sanitize_bicep()` escape special characters before interpolating user data into Terraform/Bicep templates
- **XML escaping**: `xml_escape()` applied to all user-sourced data in PDF report generation (reportlab Paragraph elements)
- **Webhook validation token**: Regex pattern validation (`^[A-Za-z0-9_-]+$`) prevents reflected content injection via the Graph validation handshake
- **Webhook clientState**: Secret value validation on incoming Graph notifications to prevent spoofed webhook calls
- **HMAC-SHA256 outbound webhooks**: All outbound webhook deliveries signed with `X-Signature-256` header
- **Tenant ID format**: GUID format validation on webhook notification tenant IDs
- **Sort field validation**: `SortField` StrEnum prevents arbitrary field injection in query ORDER BY clauses
- **Bulk export cap**: Maximum 500 identities per bulk export request
- **Pydantic validation**: All request bodies validated by Pydantic v2 with strict types, min/max constraints

### AI Security

- **Prompt injection prevention**: `_sanitize_for_prompt()` strips control characters and truncates identity-sourced data before inclusion in Foundry prompts
- **Response bounding**: AI responses capped at 5,000 characters
- **HTML stripping**: AI responses sanitized to remove HTML tags
- **Token usage logging**: Prompt and completion token counts logged for cost monitoring
- **Sanitized error logging**: Foundry endpoint URLs and keys are never included in error logs

### HTTP Security Headers

Applied via `SecurityHeadersMiddleware` on all responses:

| Header | Value |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` (production only) |

### Infrastructure Security

- **OIDC authentication**: GitHub Actions uses federated credentials -- no long-lived secrets for CI/CD
- **Managed identity**: Service-to-service communication uses Azure managed identity, never connection strings
- **Key Vault RBAC**: Deployer gets Key Vault Administrator; application managed identity gets Key Vault Secrets User (least privilege)
- **ACR RBAC**: Managed identity gets AcrPull role -- no admin credentials
- **Redis TLS**: Enforced in production (non-SSL port disabled)
- **Cosmos DB**: Session consistency, serverless tier, managed identity data contributor role
- **Trivy scanning**: Container image vulnerability scanning in CI pipeline (HIGH + CRITICAL)
- **tfsec scanning**: Terraform static analysis for misconfigurations in CI pipeline

---

## Infrastructure

### Terraform Modules

All infrastructure is defined as Terraform modules under `infra/`:

| Module | Resources |
|--------|-----------|
| **bootstrap** | Azure Storage Account for Terraform remote state |
| **identity** | Entra ID app registration (multi-tenant), 3 app roles, Microsoft Graph API permissions, service principal, client secret, user-assigned managed identity, OIDC federated credentials |
| **security** | Azure Key Vault (RBAC mode) with 6 secrets |
| **data** | Cosmos DB serverless account + 18 containers (with TTL policies), Azure Cache for Redis (Standard C1, TLS 1.2) |
| **compute** | ACR (Basic), Container App Environment, backend Container App (0.5 CPU, 1Gi, 1-10 replicas), frontend Container App (0.25 CPU, 0.5Gi, 1-5 replicas), 5 scheduled jobs |
| **observability** | Log Analytics Workspace, Application Insights |

### Deployment

1. **Bootstrap state backend**
   ```bash
   cd infra/bootstrap
   terraform init && terraform apply
   ```

2. **Deploy all infrastructure**
   ```bash
   cd infra/envs/prod
   terraform init && terraform plan
   terraform apply
   ```

### Scaling Configuration

| Service | Min Replicas | Max Replicas | Scale Rule |
|---------|-------------|-------------|-----------|
| Backend | 1 | 10 | HTTP: 50 concurrent requests |
| Frontend | 1 | 5 | HTTP: 100 concurrent requests |

---

## CI/CD

### Workflows

| Workflow | Trigger | Jobs |
|----------|---------|------|
| **CI** | Push/PR to `main` | Backend lint + test (Ruff, pytest), Frontend typecheck + build, Trivy scan, tfsec scan |
| **Deploy Backend** | Push to `main` (backend/** changes) | OIDC auth, ACR build/push, Container App update, health smoke test |
| **Deploy Frontend** | Push to `main` (frontend/** changes) | OIDC auth, ACR build/push, Container App update, smoke test |
| **Terraform Plan** | PR to `main` (infra/** changes) | OIDC auth, terraform plan, post plan as PR comment |
| **Terraform Apply** | Push to `main` (infra/** changes) | OIDC auth, terraform apply (requires `prod` environment approval) |

All deployment workflows use **OIDC federated credentials** -- no stored secrets or service principal passwords.

---

## Testing

### Running Tests

```bash
# Backend tests (104 tests)
cd backend
pip install -e ".[dev]"
pytest

# Frontend type checking
cd frontend
npm install
npx tsc --noEmit
```

### Test Coverage

| Test File | Tests | Scope |
|-----------|-------|-------|
| `test_auth.py` | 3 | Health endpoints, local mode auth bypass, role verification |
| `test_ingest.py` | 14 | Audit/sign-in log parsing, identity endpoints, tenant-ID cross-tenant rejection |
| `test_recommendations.py` | 25 | Permission mapping, role matching, IaC export (Terraform/Bicep/ARM), API endpoints |
| `test_drift.py` | 21 | First-seen detection, z-score anomaly, risk scoring, drift alert CRUD |
| `test_best_practices.py` | 19 | All 6 rules, compliance scoring, API endpoints with filtering |
| `test_dashboard.py` | 8 | Dashboard aggregation, trends, narrative endpoints |
| `test_webhooks.py` | 14 | Webhook validation, notification processing, subscriptions, reports, settings |

**Total: 104 tests**

All tests use `httpx.AsyncClient` with `ASGITransport` for full request-response testing against the FastAPI app with mocked Cosmos DB and Redis dependencies.

---

## License

This project is proprietary. All rights reserved.
