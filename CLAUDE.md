# Entra ID Least Privilege Analyzer

## Project Structure
- `backend/` — Python FastAPI API server
- `frontend/` — React 18 + Vite 5 + Tailwind CSS 3
- `infra/` — Terraform modules for Azure deployment
- `shared/` — Static data files (permission mappings, built-in role catalogs)

## Stack
- **Backend**: Python 3.12, FastAPI, Pydantic v2, azure-cosmos (async), msal
- **Frontend**: React 18, TypeScript, Vite 5, Tailwind CSS 3, @azure/msal-react, @tanstack/react-query
- **Database**: Azure Cosmos DB (NoSQL API), partition key = `/tenantId` on all containers
- **Cache**: Azure Cache for Redis
- **Auth**: Multi-tenant Entra ID (MSAL), OBO flow for Graph API calls
- **AI**: Microsoft Foundry via FoundryClient wrapper
- **IaC**: Terraform
- **CI/CD**: GitHub Actions

## Conventions
- All Cosmos DB access goes through `CosmosRepo` in `backend/app/services/cosmos.py`
- Every repo method requires `tenant_id` as first param (extracted from JWT `tid` claim)
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
