# Entra ID Least Privilege Analyzer

## Project Structure

- `backend/` — Python FastAPI API server
- `frontend/` — React 18 + Vite 5 + Tailwind CSS 3
- `infra/` — Terraform modules for Azure deployment
- `shared/` — Static data files (permission mappings, built-in role catalogs)

## Stack

- **Backend**: Python 3.12, FastAPI, Pydantic v2, azure-cosmos (async), msal
- **Frontend**: React 18, TypeScript, Vite 5, Tailwind CSS 3, @azure/msal-react, @tanstack/react-query
- **Database**: Azure Cosmos DB (NoSQL API), database-per-project architecture (master DB + one DB per project)
- **Cache**: Azure Cache for Redis
- **Auth**: Multi-tenant Entra ID (MSAL), OBO flow for Graph API calls
- **AI**: Microsoft Foundry via FoundryClient wrapper
- **IaC**: Terraform
- **CI/CD**: GitHub Actions

## Conventions

- Cosmos DB uses database-per-project isolation:
  - `MasterRepo` in `backend/app/services/master_repo.py` — singleton for platform metadata (projects, members, scans, schedules, alerts) in `entra-master` database
  - `ProjectRepo` in `backend/app/services/project_repo.py` — one instance per project database (`project-{project_id}`), cached via `ProjectRepoCache`
  - `ProjectDatabaseManager` in `backend/app/services/project_db_manager.py` — provisions/deletes project databases
  - `BatchWriter` in `backend/app/services/batch_writer.py` — Cosmos transactional batch writes with fallback
- Repo methods do NOT take `tenant_id` as first param — the database IS the isolation boundary
- Auth: `backend/app/auth/deps.py` provides `CurrentUser` and `require_role()` dependencies
- LOCAL_MODE=true skips auth and returns a mock user
- FoundryClient in `backend/app/services/foundry.py` — never call SDK from routes directly
- Frontend API calls go through typed hooks in `frontend/src/api/hooks.ts`
- Dark mode via Tailwind `darkMode: 'class'` — toggle in Header

## Commands

- Backend dev: `cd backend && pip install -e ".[dev]" && uvicorn app.main:app --reload`
- Frontend dev: `cd frontend && npm install && npm run dev`
- Backend tests: `cd backend && pytest`
- Frontend typecheck: `cd frontend && npx tsc --noEmit`
- Full stack: `docker-compose up`

## App Roles

- `SecurityEngineer` — drift alerts, identity deep-dive, action timeline
- `IAMAdmin` — recommendations, exports, best practices, settings
- `Executive` — dashboard, summary views, reports

## File Inventory

### Backend — `backend/app/`

#### Auth (`auth/`)

- `deps.py` — `CurrentUser` dependency, `require_role()`, LOCAL_MODE mock user
- `jwt.py` — Entra ID JWT token validation
- `obo.py` — On-Behalf-Of flow for Graph API calls

#### Models (`models/`)

- `tenant.py` — Tenant registration model
- `identity.py` — Identity profile (users, SPs, groups)
- `action.py` — Action event (audit log entry)
- `role.py` — Role assignment and recommendation models
- `drift.py` — Drift alert model
- `best_practice.py` — Best practice violation model
- `narrative.py` — `DashboardSummary`, `DashboardTrends`, `AnalyticsData` response models
- `export.py` — Export/report request models
- `project.py` — Project and project membership models

#### Services (`services/`)

- `master_repo.py` — `MasterRepo` class — platform metadata (projects, members, scans, schedules, alerts) in `entra-master` database
- `project_repo.py` — `ProjectRepo` class — per-project analysis data with RU tracking and batch operations
- `project_repo_cache.py` — `ProjectRepoCache` — caches ProjectRepo instances by database name
- `project_db_manager.py` — `ProjectDatabaseManager` — provisions/deletes project databases
- `batch_writer.py` — `BatchWriter` — Cosmos transactional batch writes with concurrent flush
- `cosmos_schema.py` — Container definitions (MASTER_CONTAINERS + PROJECT_CONTAINERS)
- `redis_cache.py` — Redis cache wrapper
- `graph_ingest.py` — Microsoft Graph API data ingestion
- `graph_roles.py` — Graph API role/directory role queries
- `role_mapper.py` — Maps actions to required roles
- `role_recommender.py` — Generates least-privilege role recommendations
- `drift_detector.py` — Detects anomalous/first-seen actions
- `risk_scorer.py` — Computes identity risk scores
- `best_practice_analyzer.py` — Evaluates Entra ID best practice compliance
- `narrative_engine.py` — AI-powered dashboard narrative generation (uses Foundry)
- `foundry.py` — `FoundryClient` wrapper for Microsoft Foundry SDK
- `report_generator.py` — PDF/PPTX report generation
- `iac_exporter.py` — Terraform/Bicep export for role assignments
- `webhook.py` — Outbound webhook delivery
- `crypto.py` — Encryption utilities for stored credentials
- `permission_validator.py` — Validates permission scopes

#### Routers (`routers/`)

- `project_api.py` — Project-scoped API: dashboard, analytics, identities, recommendations, drift, best practices, settings, reports
- `projects.py` — Project CRUD, membership management, and `/me` endpoint
- `scans.py` — Scan trigger, status, and SSE event streaming
- `health.py` — Health check endpoint (liveness + readiness via MasterRepo)

#### Pipelines (`pipelines/`)

- `ingest_pipeline.py` — Orchestrates Graph API ingestion → analysis
- `recommendation_pipeline.py` — Runs role recommendation analysis
- `baseline_pipeline.py` — Establishes action baseline for drift detection
- `drift_pipeline.py` — Runs drift detection against baseline

#### Data (`data/`)

- `permission_catalog.py` — Loads `shared/permission_mappings.json`
- `builtin_roles.py` — Loads `shared/builtin_roles_*.json`

#### Backend Root Files

- `main.py` — FastAPI app setup, middleware, router mounting
- `config.py` — Settings via Pydantic `BaseSettings` (env vars)
- `observability.py` — OpenTelemetry + logging setup

### Frontend — `frontend/src/`

#### Auth (`auth/`)

- `msal.ts` — MSAL configuration and PublicClientApplication
- `useAuth.ts` — Auth hook (login, logout, acquireToken)
- `LoginGate.tsx` — Unauthenticated landing / login prompt

#### API (`api/`)

- `client.ts` — Axios instance with auth interceptor
- `types.ts` — All TypeScript interfaces (Identity, DriftAlert, Recommendation, AnalyticsData, etc.)
- `hooks.ts` — TanStack Query hooks for project-scoped API (useIdentities, useDashboard, useAnalytics, etc.)
- `projectHooks.ts` — Hooks for project CRUD and membership

#### Pages (`pages/`)

- `ProjectsHomePage.tsx` — Project list (no AppShell)
- `ProjectCreatePage.tsx` — New project form
- `DashboardPage.tsx` — Executive KPI dashboard
- `AnalyticsPage.tsx` — Activity, permission & security posture analytics (14 widgets, time range selector)
- `IdentitiesPage.tsx` — Identity list with filters
- `IdentityDetailPage.tsx` — Single identity deep-dive
- `RecommendationsPage.tsx` — Role recommendation list
- `RecommendationDetailPage.tsx` — Single recommendation with role diff
- `DriftPage.tsx` — Drift alert list
- `DriftDetailPage.tsx` — Single drift alert detail
- `BestPracticesPage.tsx` — Best practice violation list
- `BestPracticeDetailPage.tsx` — Single violation detail
- `ScanPage.tsx` — Scan trigger and status
- `ReportsPage.tsx` — Report generation and download
- `ProjectMembersPage.tsx` — Team member management
- `SettingsPage.tsx` — Project settings

#### Components — Layout (`components/layout/`)

- `AppShell.tsx` — Sidebar + Header + Outlet wrapper
- `Sidebar.tsx` — Navigation sidebar with Analyze/Manage sections
- `Header.tsx` — Top bar with dark mode toggle, user menu
- `RoleGate.tsx` — Conditional render by app role

#### Components — Common (`components/common/`)

- `Tooltip.tsx` — Reusable tooltip
- `DataTable.tsx` — Sortable, paginated table
- `LoadingSpinner.tsx` — Loading indicator
- `EmptyState.tsx` — Empty state placeholder
- `SeverityBadge.tsx` — Severity level badge (critical/high/medium/low)
- `AINarrativeCard.tsx` — AI-generated narrative display
- `JsonViewer.tsx` — Collapsible JSON tree

#### Components — Dashboard (`components/dashboard/`)

- `RiskScoreCard.tsx` — Risk score gauge
- `IdentitySummaryCard.tsx` — Identity count by type
- `DriftSummaryCard.tsx` — Drift alert summary
- `TopRiskyIdentities.tsx` — Top 5 risky identities list
- `TrendChart.tsx` — SVG line chart with time range tabs

#### Components — Analytics (`components/analytics/`)

- `KpiStrip.tsx` — 5-number KPI row
- `ActivitySparkline.tsx` — SVG daily volume line chart
- `HorizontalBarChart.tsx` — Reusable horizontal bar chart
- `DonutChart.tsx` — Reusable SVG donut chart
- `MostActiveIdentities.tsx` — Ranked identity list by action count
- `TopResources.tsx` — Ranked resource list
- `PermissionUtilization.tsx` — Used vs unused permission gauge
- `OverprivilegedCard.tsx` — Overprivileged identity count card
- `StaleIdentities.tsx` — 30/60/90d stale identity breakdown
- `RecentDriftActivity.tsx` — Recent drift alert timeline

#### Components — Domain

- `identities/IdentityTable.tsx` — Identity list table
- `identities/IdentityDetail.tsx` — Identity detail panel
- `identities/ActionTimeline.tsx` — Action event timeline
- `drift/DriftAlertTable.tsx` — Drift alert table
- `drift/DriftTimeline.tsx` — Drift event timeline
- `drift/AcknowledgeDialog.tsx` — Acknowledge drift alert dialog
- `recommendations/RecommendationList.tsx` — Recommendation list
- `recommendations/RoleDiff.tsx` — Current vs recommended role diff
- `recommendations/PermissionDelta.tsx` — Permission add/remove view
- `recommendations/CustomRolePreview.tsx` — Custom role definition preview
- `recommendations/ExportPanel.tsx` — IaC export panel
- `best-practices/ViolationList.tsx` — Violation list
- `best-practices/RemediationSteps.tsx` — Remediation guidance
- `best-practices/ComplianceGauge.tsx` — Compliance score gauge

#### Store (`store/`)

- `projectContext.tsx` — `ProjectProvider` + `useProjectContext()` — current project ID from URL
- `tenantContext.tsx` — Legacy tenant context

#### Frontend Root Files

- `App.tsx` — Route definitions, auth gating, project provider
- `main.tsx` — React DOM entry point, MSAL provider

### Infrastructure — `infra/`

- `bootstrap/main.tf` — Resource group, storage account for TF state
- `modules/identity/` — Entra ID app registrations, managed identities
- `modules/data/` — Cosmos DB account, databases, containers; Redis
- `modules/compute/` — Container Apps environment, apps, ACR
- `modules/security/` — Key Vault, secrets, RBAC
- `modules/observability/` — Log Analytics, App Insights
- `envs/prod/` — Production environment composition

### Shared Data — `shared/`

- `permission_mappings.json` — Graph API action → permission scope mapping
- `builtin_roles_entra.json` — Entra ID built-in role definitions
- `builtin_roles_azure.json` — Azure RBAC built-in role definitions

### Root Config

- `docker-compose.yml` — Local dev stack (backend, frontend, Cosmos emulator, Redis)
- `backend/Dockerfile` — Backend container image
- `backend/pyproject.toml` — Python dependencies and project config
- `frontend/Dockerfile` — Frontend container image
- `frontend/package.json` — Node dependencies
- `frontend/vite.config.ts` — Vite build config with path aliases
- `frontend/tailwind.config.ts` — Tailwind theme (brand colors, dark mode)
- `frontend/tsconfig.json` — TypeScript config
