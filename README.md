# Entra Permissions Analyzer

A multi-tenant SaaS application that connects to Microsoft Entra ID tenants via Microsoft Graph API, analyzes audit/sign-in/activity logs to build per-identity action profiles, recommends least-privilege roles, detects permission drift in near-real-time, surfaces best-practice violations, and presents everything in a persona-aware executive dashboard with AI-generated narratives.

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
- Delta query support for incremental sync with configurable schedule (default: every 6 hours)
- Full action timeline with resource context and result status

### Least-Privilege Role Recommender
- Maps observed actions to required Microsoft Graph API permissions
- Compares current role assignments against minimum required permissions
- Identifies excessive privileges with side-by-side permission delta view
- Recommends best-matching built-in roles (Entra ID and Azure RBAC) with coverage scoring
- Generates custom role definitions when no built-in role fits
- Computes a reduction score showing how much privilege can be removed
- Exports recommendations to **Terraform HCL**, **Bicep**, and **ARM JSON** templates

### Permission Drift Detection
- **Two-layer detection engine:**
  - **First-seen detection** — flags any action not previously observed in an identity's baseline
  - **Z-score anomaly detection** — rolling statistics (mean, stddev) per identity per action; z > 3.0 = High, z > 2.0 = Medium, z > 1.5 = Low severity
- Rolling 30-day baselines computed daily
- Identities with < 7 days of baseline data use first-seen only
- Drift alert workflow: Open, Acknowledged, Escalated, Resolved
- Composite risk scoring (0-100) weighted across drift alerts, overprivilege, permanent admin roles, and stale access

### Best Practice Advisor
- Rule engine evaluating identities against Entra ID and Azure RBAC best practices:

| Rule | What It Checks | Priority |
|------|---------------|----------|
| Stale Identity | No sign-in activity in 30/60/90 days | Medium / High / Critical |
| Permanent Admin | Global Admin or other admin roles without time-bound assignment | Critical / High |
| No PIM | Privileged roles not managed via Privileged Identity Management | High |
| Overprivileged | More permissions assigned than observed in use | Medium |
| Separation of Duties | Single identity holding conflicting admin roles | High |
| Role-Assignable Group | Groups that can be assigned directory roles | Medium |

- Compliance score (0-100%) with priority-weighted penalty deductions
- Actionable remediation steps for each violation

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

### Real-Time Webhooks
- Microsoft Graph change notification subscriptions for near-real-time audit log updates
- Webhook validation handshake (validationToken echo as text/plain)
- `clientState` secret validation on incoming notifications
- Automatic processing through the same ingest pipeline as batch sync

### Report Export
- Executive reports in **PDF** (via reportlab) and **PowerPoint PPTX** (via python-pptx)
- Risk summary tables, compliance metrics, top risky identities
- JSON fallback when optional report libraries are not installed

### Persona-Aware Access Control
Three application roles with scoped access:

| Role | Access |
|------|--------|
| **SecurityEngineer** | Drift alerts, identity deep-dive, action timeline, baselines |
| **IAMAdmin** | Recommendations, IaC exports, best practices, settings, sync, onboarding, subscriptions |
| **Executive** | Dashboard, summary views, reports, AI narratives |

---

## Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    Azure Container Apps                  │
                    │  ┌──────────────┐              ┌──────────────────────┐ │
  Users ──MSAL──────┤  │   Frontend   │──REST API───▶│      Backend         │ │
  (Browser)         │  │  React + Vite │              │    FastAPI (Python)  │ │
                    │  │   Tailwind    │              │                      │ │
                    │  └──────────────┘              │  ┌──────────────────┐│ │
                    │                                │  │  Auth (JWT/OBO)  ││ │
                    │                                │  ├──────────────────┤│ │
                    │                                │  │  14 Routers      ││ │
                    │                                │  │  (34 endpoints)  ││ │
                    │                                │  ├──────────────────┤│ │
                    │                                │  │  14 Services     ││ │
                    │                                │  ├──────────────────┤│ │
                    │                                │  │  4 Pipelines     ││ │
                    │                                │  └──────────────────┘│ │
                    │                                └──────────┬───────────┘ │
                    │                                           │             │
                    │  ┌─────────────────────────────────────┐  │             │
                    │  │      5 Scheduled Jobs (CRON)        │  │             │
                    │  │  sync ─▶ baselines ─▶ drift ─▶ recs │  │             │
                    │  │  ─▶ narratives                      │  │             │
                    │  └─────────────────────────────────────┘  │             │
                    └───────────────────────────────────────────┘             │
                                           │                                 │
             ┌─────────────────────────────┼─────────────────────────────────┘
             │                             │
             ▼                             ▼
  ┌────────────────────┐       ┌──────────────────────┐      ┌──────────────┐
  │  Azure Cosmos DB   │       │  Azure Cache for     │      │  Microsoft   │
  │  (NoSQL, Serverless)│      │  Redis               │      │  Graph API   │
  │                    │       │                      │      │              │
  │  9 containers      │       │  Dashboard cache     │      │  Audit logs  │
  │  Partition: /tenantId│     │  Rate limiting       │      │  Sign-ins    │
  └────────────────────┘       └──────────────────────┘      │  Roles       │
                                                             │  Webhooks    │
                                                             └──────────────┘
             ┌──────────────────┐       ┌──────────────────┐
             │  Azure Key Vault │       │  Azure AI Foundry │
             │  6 secrets       │       │  GPT-4o narratives │
             └──────────────────┘       └──────────────────┘
```

### Multi-Tenant Data Isolation

Every Cosmos DB container uses `/tenantId` as the partition key. All repository methods require `tenant_id` as the first parameter, extracted from the authenticated user's JWT `tid` claim. Cross-tenant data access is structurally impossible at the data layer.

### Hybrid Sync Architecture

| Method | Trigger | Frequency | Mechanism |
|--------|---------|-----------|-----------|
| Batch sync | CRON job | Every 6 hours | Delta queries with stored delta links |
| Webhooks | Graph change notification | Near-real-time | Graph pushes audit events to `/api/webhooks/graph` |

### Scheduled Job Pipeline

Jobs run as Azure Container Apps Jobs in sequence:

| Job | Schedule | What It Does |
|-----|----------|-------------|
| `sync-tenant` | `0 */6 * * *` | Fetch new audit/sign-in logs from Graph API |
| `compute-baselines` | `0 2 * * *` | Calculate 30-day rolling baseline statistics |
| `detect-drift` | `0 3 * * *` | Run first-seen + z-score anomaly detection |
| `generate-recommendations` | `0 4 * * *` | Compute least-privilege role recommendations |
| `generate-narratives` | `0 5 * * *` | Generate AI narrative digests via Foundry |

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
| Technology | Purpose |
|-----------|---------|
| Azure Container Apps | Application hosting (backend, frontend, scheduled jobs) |
| Azure Cosmos DB | NoSQL database (serverless, 9 containers) |
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
├── .github/workflows/          # 5 CI/CD workflows
│   ├── ci.yml                  # Lint, test, type-check, security scan
│   ├── deploy-backend.yml      # Build and deploy backend Container App
│   ├── deploy-frontend.yml     # Build and deploy frontend Container App
│   ├── infra-plan.yml          # Terraform plan on PRs
│   └── infra-apply.yml         # Terraform apply on merge
├── backend/
│   ├── app/
│   │   ├── auth/               # JWT validation, OBO flow, role dependencies
│   │   │   ├── jwt.py          # Multi-tenant JWT validator (OIDC discovery, JWKS caching)
│   │   │   ├── deps.py         # CurrentUser, require_role(), validate_tenant_access()
│   │   │   └── obo.py          # On-Behalf-Of token provider for Graph API
│   │   ├── data/               # Static catalogs loaded from shared/ JSON
│   │   │   ├── permission_catalog.py
│   │   │   └── builtin_roles.py
│   │   ├── models/             # 8 Pydantic v2 model files
│   │   ├── pipelines/          # 4 pipeline orchestrators
│   │   ├── routers/            # 14 API router files (34 endpoints)
│   │   ├── services/           # 14 service files (business logic)
│   │   ├── config.py           # pydantic-settings (18 configuration fields)
│   │   ├── main.py             # FastAPI app factory, middleware, lifespan
│   │   └── observability.py    # OpenTelemetry + App Insights setup
│   ├── jobs/                   # 5 Container Apps Job entry points
│   ├── tests/                  # 7 test files, 104 test functions
│   ├── Dockerfile              # Multi-stage: dev (hot-reload) / prod (4 workers)
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── auth/               # MSAL config, useAuth hook, LoginGate
│   │   ├── api/                # ApiClient, typed hooks (20+), TypeScript interfaces
│   │   ├── components/         # 29 React components across 7 categories
│   │   ├── pages/              # 11 page components
│   │   ├── store/              # Tenant context provider
│   │   └── hooks/              # Dark mode toggle
│   ├── Dockerfile              # Multi-stage: build / prod (nginx)
│   ├── package.json
│   ├── tailwind.config.ts
│   └── vite.config.ts
├── infra/
│   ├── bootstrap/              # Remote state backend (Azure Storage)
│   ├── modules/
│   │   ├── identity/           # Entra app registration, managed identity, OIDC
│   │   ├── security/           # Key Vault with 6 secrets
│   │   ├── data/               # Cosmos DB (9 containers) + Redis
│   │   ├── compute/            # ACR, Container Apps, 5 scheduled jobs
│   │   └── observability/      # Log Analytics + Application Insights
│   └── envs/prod/              # Root module composition
├── shared/                     # Static data files
│   ├── permission_mappings.json
│   ├── builtin_roles_entra.json
│   └── builtin_roles_azure.json
├── docker-compose.yml          # Local dev: backend + frontend + Redis
├── .env.example
└── CLAUDE.md
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

### Backend Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOCAL_MODE` | No | `false` | Skip authentication, return mock user (dev only) |
| `BACKEND_PORT` | No | `8000` | Server listen port |
| `CORS_ORIGINS` | No | `http://localhost:5173` | Comma-separated allowed origins |
| `AZURE_CLIENT_ID` | Prod | `""` | Entra ID application (client) ID |
| `AZURE_CLIENT_SECRET` | Prod | `""` | Entra ID client secret |
| `AZURE_TENANT_ID` | Prod | `""` | Entra ID tenant ID (for OBO flow) |
| `COSMOS_ENDPOINT` | Prod | `https://localhost:8081` | Cosmos DB account endpoint |
| `COSMOS_KEY` | Prod | `""` | Cosmos DB access key |
| `COSMOS_DATABASE` | No | `entra-analyzer` | Cosmos DB database name |
| `REDIS_HOST` | No | `localhost` | Redis hostname |
| `REDIS_PORT` | No | `6379` | Redis port |
| `REDIS_PASSWORD` | Prod | `""` | Redis password |
| `REDIS_SSL` | No | `false` | Enable TLS for Redis |
| `KEYVAULT_URL` | Prod | `""` | Azure Key Vault URL |
| `AZURE_FOUNDRY_ENDPOINT` | No | `""` | Azure AI Foundry endpoint |
| `AZURE_FOUNDRY_KEY` | No | `""` | Azure AI Foundry API key |
| `AZURE_FOUNDRY_MODEL` | No | `gpt-4o` | AI model deployment name |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | No | `""` | Application Insights connection string |

### Frontend Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_APP_CLIENT_ID` | Prod | — | Entra ID application client ID |
| `VITE_API_BASE_URL` | No | `/api` | Backend API base URL |
| `VITE_LOCAL_MODE` | No | `false` | Skip MSAL authentication (dev only) |

---

## API Reference

### Health & Tenants

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/healthz` | Public | Liveness probe |
| GET | `/readyz` | Public | Readiness probe (checks Cosmos DB) |
| GET | `/api/tenants/me` | Authenticated | Current tenant info from JWT |
| POST | `/api/tenants/onboard` | IAMAdmin | Register tenant, trigger initial sync |

### Identity & Actions

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/tenants/{tid}/identities` | Authenticated | Paginated, filterable identity list |
| GET | `/api/tenants/{tid}/identities/{iid}` | Authenticated | Identity detail |
| GET | `/api/tenants/{tid}/identities/{iid}/actions` | SecurityEngineer, IAMAdmin | Action history timeline |

### Sync

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/tenants/{tid}/sync/trigger` | IAMAdmin | Trigger manual sync |
| GET | `/api/tenants/{tid}/sync/status` | IAMAdmin | Current sync state |

### Recommendations & Exports

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/tenants/{tid}/recommendations` | IAMAdmin, SecurityEngineer | Paginated recommendation list |
| GET | `/api/tenants/{tid}/recommendations/{iid}` | IAMAdmin, SecurityEngineer | Recommendation detail per identity |
| POST | `/api/tenants/{tid}/recommendations/compute` | IAMAdmin | Trigger batch computation (async, returns 202) |
| GET | `/api/tenants/{tid}/exports/{iid}?format=terraform\|bicep\|arm` | IAMAdmin | Export IaC for an identity |
| POST | `/api/tenants/{tid}/exports/bulk` | IAMAdmin | Bulk export (max 500 identities) |

### Drift Detection

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/tenants/{tid}/drift-alerts` | SecurityEngineer, IAMAdmin | Filterable drift alert list |
| GET | `/api/tenants/{tid}/drift-alerts/{aid}` | SecurityEngineer, IAMAdmin | Alert detail |
| PATCH | `/api/tenants/{tid}/drift-alerts/{aid}` | SecurityEngineer, IAMAdmin | Update status (acknowledge/escalate/resolve) |
| POST | `/api/tenants/{tid}/drift-alerts/detect` | IAMAdmin | Trigger on-demand detection |
| GET | `/api/tenants/{tid}/baselines/{iid}` | SecurityEngineer | View baseline statistics |

### Best Practices

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/tenants/{tid}/best-practices` | IAMAdmin, SecurityEngineer | Filterable violation list |
| GET | `/api/tenants/{tid}/best-practices/summary` | IAMAdmin, SecurityEngineer, Executive | Aggregated compliance score |
| GET | `/api/tenants/{tid}/best-practices/{vid}` | IAMAdmin, SecurityEngineer | Violation detail with remediation |
| POST | `/api/tenants/{tid}/best-practices/evaluate` | IAMAdmin | Trigger evaluation |

### Dashboard & Narratives

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/tenants/{tid}/dashboard` | All roles | Risk score, counts, summary |
| GET | `/api/tenants/{tid}/dashboard/trends` | All roles | 30-day time-series data |
| GET | `/api/tenants/{tid}/narratives/executive` | All roles | AI executive digest |
| GET | `/api/tenants/{tid}/narratives/identity/{iid}` | SecurityEngineer, IAMAdmin | AI identity summary |
| POST | `/api/tenants/{tid}/narratives/refresh` | IAMAdmin | Force regenerate narratives |

### Webhooks & Subscriptions

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/webhooks/graph` | Public (Graph callback) | Receive Graph change notifications |
| POST | `/api/tenants/{tid}/subscriptions/create` | IAMAdmin | Create Graph notification subscription |
| GET | `/api/tenants/{tid}/subscriptions` | IAMAdmin | List active subscriptions |

### Reports & Settings

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/tenants/{tid}/reports/executive?format=pdf\|pptx` | Executive, IAMAdmin | Download executive report |
| GET | `/api/tenants/{tid}/settings` | IAMAdmin | Get tenant configuration |
| PUT | `/api/tenants/{tid}/settings` | IAMAdmin | Update tenant settings |

**Total: 34 endpoints across 14 routers.**

---

## Data Model

### Cosmos DB Containers

All containers use `/tenantId` as the partition key for tenant isolation.

| Container | ID Strategy | TTL | Contents |
|-----------|-------------|-----|----------|
| `tenant_configs` | `{tenantId}` | None | Tenant settings (display name, sync schedule, baseline window) |
| `identity_profiles` | `{identityType}_{objectId}` | None | User/SP/MI/Group profiles with observed actions and current roles |
| `action_events` | UUID | 90 days | Parsed audit log, sign-in log, and activity log events |
| `sync_state` | `{syncType}` | None | Delta links, timestamps, webhook subscription state |
| `role_recommendations` | `{identityId}` | None | Computed recommendations with built-in matches and custom roles |
| `drift_alerts` | UUID | None | Drift detection alerts with severity, status, and evidence |
| `baselines` | `{identityId}` | None | Rolling 30-day action frequency statistics (mean, stddev) |
| `best_practice_violations` | `{identityId}_{violationType}` | None | Best practice evaluation results with remediation steps |
| `narratives` | `{scope}_{scopeId}` | 24 hours | AI-generated narrative text |

### Pydantic Models

| Model | Key Fields |
|-------|-----------|
| `IdentityProfile` | identity_type, display_name, observed_actions[], current_roles[], risk_score, first_seen, last_seen |
| `ActionEvent` | action_name, resource_name, action_result, source (audit/sign-in/activity), timestamp |
| `RoleRecommendation` | current_roles, required_permissions, gaps[], best_builtin_match, alternatives[], custom_role, reduction_score |
| `DriftAlert` | drift_type (first_seen/frequency_anomaly), severity, status, action_name, z_score, evidence |
| `BaselineStats` | action_name, resource_name, mean, stddev, sample_count, window_start/end |
| `BestPracticeViolation` | violation_type, priority, description, remediation_steps, affected_identity |
| `Narrative` | scope (executive/identity/drift/recommendation), content, generated_at |
| `DashboardSummary` | total_identities, avg_risk_score, high_risk_count, drift_alerts_open, compliance_score |

---

## Security

### Authentication & Authorization

- **Multi-tenant Entra ID**: MSAL with `common` authority accepts users from any Azure AD tenant
- **JWT validation**: Multi-tenant issuer validation (`https://login.microsoftonline.com/{tid}/v2.0`), RS256 signature verification, JWKS key caching with 1-hour rotation
- **On-Behalf-Of (OBO) flow**: Backend exchanges user tokens for Graph API tokens to call Microsoft Graph on behalf of the user's tenant
- **Role-based access control**: Three app roles (SecurityEngineer, IAMAdmin, Executive) enforced at every endpoint via `require_role()` dependency
- **Tenant access validation**: Every tenant-scoped endpoint verifies the JWT `tid` claim matches the requested `tenant_id`
- **LOCAL_MODE**: Single flag that bypasses all auth for development. Never enabled in staging or production.

### Data Protection

- **Tenant isolation**: Cosmos DB partition key `/tenantId` on all 9 containers ensures queries never cross tenant boundaries
- **Parameterized queries**: All Cosmos DB queries use `@param` binding — no string interpolation of user values
- **Cosmos field stripping**: `ConfigDict(extra="ignore")` on all API-returned models prevents Cosmos metadata leakage (`_rid`, `_self`, `_etag`)
- **Secrets management**: All sensitive values (Cosmos key, Redis password, Foundry key, client secret, App Insights connection string) stored in Azure Key Vault — never in environment variables or code

### Input Validation & Sanitization

- **IaC template injection prevention**: `_sanitize_hcl()` and `_sanitize_bicep()` escape special characters before interpolating user data into Terraform/Bicep templates
- **XML escaping**: `xml_escape()` applied to all user-sourced data in PDF report generation (reportlab Paragraph elements)
- **Webhook validation token**: Regex pattern validation (`^[A-Za-z0-9_-]+$`) prevents reflected content injection via the Graph validation handshake
- **Webhook clientState**: Secret value validation on incoming Graph notifications to prevent spoofed webhook calls
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

- **OIDC authentication**: GitHub Actions uses federated credentials — no long-lived secrets for CI/CD
- **Managed identity**: Service-to-service communication uses Azure managed identity, never connection strings
- **Key Vault RBAC**: Deployer gets Key Vault Administrator; application managed identity gets Key Vault Secrets User (least privilege)
- **ACR RBAC**: Managed identity gets AcrPull role — no admin credentials
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
| **data** | Cosmos DB serverless account + 9 containers (with TTL policies), Azure Cache for Redis (Standard C1, TLS 1.2) |
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

All deployment workflows use **OIDC federated credentials** — no stored secrets or service principal passwords.

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
