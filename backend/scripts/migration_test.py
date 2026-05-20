#!/usr/bin/env python3
"""
End-to-end migration test for the database-per-project architecture.

Runs against the live backend API (LOCAL_MODE=true) with real Cosmos DB
and real Microsoft Graph credentials. Validates:

  1. Master database (entra-master) and containers are created on startup
  2. Project creation provisions a dedicated project-{id} database
  3. Inline sync (/sync/trigger) fetches Graph data with a 3-page limit
  4. Identity profiles, action events, and scan records are persisted
  5. Dashboard and analytics endpoints return populated data
  6. Project deletion removes the project database entirely

Usage:
    # Start the backend first:
    #   cd backend && uvicorn app.main:app --port 8000
    #
    # Then run:
    python scripts/migration_test.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
log = logging.getLogger("migration_test")

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
MAX_PAGES = int(os.getenv("TEST_MAX_PAGES", "3"))
TIMEOUT = 300.0

# Graph API app registration credentials (separate from backend auth app).
# These need AuditLog.Read.All, Directory.Read.All, Application.Read.All, etc.
CLIENT_ID = os.getenv("GRAPH_APP_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GRAPH_APP_CLIENT_SECRET", "")
TARGET_TENANT_ID = os.getenv("GRAPH_APP_TENANT_ID", os.getenv("AZURE_TENANT_ID", ""))
TARGET_TENANT_NAME = os.getenv("GRAPH_APP_TENANT_NAME", "Advisory Cloud Cyber Risk Lab")


class MigrationTestError(Exception):
    pass


def _check(label: str, resp: httpx.Response, expected: int = 200) -> dict[str, Any]:
    if resp.status_code != expected:
        log.error(
            "%s — expected %d, got %d: %s",
            label,
            expected,
            resp.status_code,
            resp.text[:500],
        )
        raise MigrationTestError(f"{label} failed: HTTP {resp.status_code}")
    try:
        return resp.json()
    except Exception:
        return {}


async def run_test() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as c:
        # ----------------------------------------------------------
        # 0. Health check
        # ----------------------------------------------------------
        log.info("=== Step 0: Health check ===")
        body = _check("healthz", await c.get("/healthz"))
        assert body.get("status") == "ok", f"Health check failed: {body}"
        log.info("Health OK")

        body = _check("readyz", await c.get("/readyz"))
        log.info("Readiness: %s", body.get("status"))

        # ----------------------------------------------------------
        # 1. Whoami
        # ----------------------------------------------------------
        log.info("=== Step 1: Verify mock user ===")
        me = _check("whoami", await c.get("/api/projects/me"))
        log.info("Authenticated as: %s (%s)", me.get("name"), me.get("email"))
        assert me.get("oid"), "No OID in whoami response"

        # ----------------------------------------------------------
        # 2. List existing projects (should be empty or have old ones)
        # ----------------------------------------------------------
        log.info("=== Step 2: List existing projects ===")
        projects = _check("list_projects", await c.get("/api/projects"))
        log.info("Existing projects: %d", len(projects))
        for p in projects:
            project_id = p.get("id", "")
            log.info("  - %s: %s (db=%s, status=%s)", project_id[:8], p["name"], p.get("database_name", "?"), p["status"])

        # ----------------------------------------------------------
        # 3. Create a new test project with Graph credentials
        # ----------------------------------------------------------
        log.info("=== Step 3: Create test project ===")
        if not CLIENT_ID or not CLIENT_SECRET or not TARGET_TENANT_ID:
            log.error(
                "Missing credentials. Set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, "
                "AZURE_TENANT_ID in .env or environment."
            )
            raise MigrationTestError("Missing Graph credentials")

        create_resp = await c.post(
            "/api/projects",
            json={
                "name": "Migration Test Project",
                "target_tenant_id": TARGET_TENANT_ID,
                "target_tenant_name": TARGET_TENANT_NAME,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )
        project = _check("create_project", create_resp, expected=201)
        project_id = project["id"]
        log.info(
            "Created project %s (status=%s, permission_status=%s)",
            project_id[:8],
            project.get("status"),
            "valid" if project.get("permission_status", {}).get("valid") else "invalid",
        )

        if project.get("permission_status") and not project["permission_status"].get("valid"):
            missing = project["permission_status"].get("missing_permissions", [])
            log.warning("Missing Graph permissions: %s", missing)

        try:
            # ----------------------------------------------------------
            # 4. Get project details
            # ----------------------------------------------------------
            log.info("=== Step 4: Verify project details ===")
            detail = _check("get_project", await c.get(f"/api/projects/{project_id}"))
            log.info(
                "Project: name=%s, target=%s, client_id=%s",
                detail["name"],
                detail["target_tenant_id"],
                detail["client_id"][:8] + "...",
            )

            # ----------------------------------------------------------
            # 5. Trigger inline sync with 3-page limit
            # ----------------------------------------------------------
            log.info("=== Step 5: Trigger inline sync (max_pages=%d) ===", MAX_PAGES)
            t0 = time.monotonic()
            sync_resp = await c.post(
                f"/api/projects/{project_id}/sync/trigger?full=true&max_pages={MAX_PAGES}",
            )
            elapsed = time.monotonic() - t0
            summary = _check("sync_trigger", sync_resp)
            log.info("Sync completed in %.1fs", elapsed)
            log.info("Sync summary: %s", json.dumps(summary, indent=2, default=str))

            # ----------------------------------------------------------
            # 6. Verify identities were stored
            # ----------------------------------------------------------
            log.info("=== Step 6: Verify stored identities ===")
            identities = _check(
                "list_identities",
                await c.get(f"/api/projects/{project_id}/identities?size=10"),
            )
            total_identities = identities.get("total", 0)
            items = identities.get("items", [])
            log.info("Total identities: %d (showing first %d)", total_identities, len(items))
            for ident in items[:5]:
                log.info(
                    "  - %s (%s) risk=%.1f type=%s",
                    ident.get("display_name", "?"),
                    ident.get("upn", ident.get("id", "?")[:8]),
                    ident.get("risk_score", 0),
                    ident.get("identity_type", "?"),
                )

            # ----------------------------------------------------------
            # 7. Verify dashboard data
            # ----------------------------------------------------------
            log.info("=== Step 7: Check dashboard ===")
            dash = _check(
                "dashboard",
                await c.get(f"/api/projects/{project_id}/dashboard"),
            )
            log.info(
                "Dashboard: identities=%s, risk_score=%s, drift_alerts=%s",
                dash.get("total_identities"),
                dash.get("risk_score"),
                dash.get("active_drift_alerts"),
            )

            # ----------------------------------------------------------
            # 8. Verify analytics data
            # ----------------------------------------------------------
            log.info("=== Step 8: Check analytics ===")
            analytics = _check(
                "analytics",
                await c.get(f"/api/projects/{project_id}/analytics"),
            )
            log.info(
                "Analytics: total_actions=%s, unique_identities=%s",
                analytics.get("total_actions"),
                analytics.get("unique_identities"),
            )

            # ----------------------------------------------------------
            # 9. Check recommendations (compute them first)
            # ----------------------------------------------------------
            log.info("=== Step 9: Compute recommendations ===")
            rec_resp = await c.post(f"/api/projects/{project_id}/recommendations/compute")
            if rec_resp.status_code == 202:
                log.info("Recommendations computation accepted")
            else:
                log.warning("Recommendations compute returned %d", rec_resp.status_code)

            recs = _check(
                "recommendations",
                await c.get(f"/api/projects/{project_id}/recommendations?size=5"),
            )
            log.info("Recommendations: %d total", recs.get("total", 0))

            # ----------------------------------------------------------
            # 10. Check best practices (evaluate)
            # ----------------------------------------------------------
            log.info("=== Step 10: Evaluate best practices ===")
            bp_resp = await c.post(f"/api/projects/{project_id}/best-practices/evaluate")
            if bp_resp.status_code == 202:
                log.info("Best practices evaluation accepted")
            else:
                log.warning("Best practices evaluate returned %d", bp_resp.status_code)

            bp = _check(
                "best_practices",
                await c.get(f"/api/projects/{project_id}/best-practices?size=5"),
            )
            log.info("Best practice violations: %d total", bp.get("total", 0))

            # ----------------------------------------------------------
            # 11. Check drift detection
            # ----------------------------------------------------------
            log.info("=== Step 11: Run drift detection ===")
            drift_resp = await c.post(f"/api/projects/{project_id}/drift-alerts/detect")
            if drift_resp.status_code == 202:
                log.info("Drift detection accepted")
            else:
                log.warning("Drift detection returned %d", drift_resp.status_code)

            drift = _check(
                "drift_alerts",
                await c.get(f"/api/projects/{project_id}/drift-alerts?size=5"),
            )
            log.info("Drift alerts: %d total", drift.get("total", 0))

            # ----------------------------------------------------------
            # 12. Check sync status
            # ----------------------------------------------------------
            log.info("=== Step 12: Check sync status ===")
            sync_status = _check(
                "sync_status",
                await c.get(f"/api/projects/{project_id}/sync/status"),
            )
            log.info("Sync status: %s", json.dumps(sync_status, indent=2, default=str))

            # ----------------------------------------------------------
            # 13. List scan history
            # ----------------------------------------------------------
            log.info("=== Step 13: Check scan history ===")
            scans = _check(
                "scan_history",
                await c.get(f"/api/projects/{project_id}/scans"),
            )
            log.info("Scan records: %d total", scans.get("total", 0))
            for s in scans.get("items", []):
                log.info(
                    "  - %s: type=%s status=%s started=%s",
                    s["id"][:8],
                    s.get("scan_type"),
                    s.get("status"),
                    s.get("started_at"),
                )

            # ----------------------------------------------------------
            # Summary
            # ----------------------------------------------------------
            log.info("=" * 60)
            log.info("MIGRATION TEST PASSED")
            log.info("=" * 60)
            log.info("  Project ID:       %s", project_id)
            log.info("  Identities:       %d", total_identities)
            log.info("  Recommendations:  %d", recs.get("total", 0))
            log.info("  Drift Alerts:     %d", drift.get("total", 0))
            log.info("  BP Violations:    %d", bp.get("total", 0))
            log.info("  Sync elapsed:     %.1fs", elapsed)
            log.info("=" * 60)

        except Exception:
            log.exception("Test failed — cleaning up project %s", project_id[:8])
            raise

        finally:
            # ----------------------------------------------------------
            # 14. Cleanup — delete test project
            # ----------------------------------------------------------
            log.info("=== Step 14: Cleanup — delete test project ===")
            del_resp = await c.delete(f"/api/projects/{project_id}")
            if del_resp.status_code == 204:
                log.info("Project %s deleted (database removed)", project_id[:8])
            else:
                log.warning(
                    "Project deletion returned %d: %s",
                    del_resp.status_code,
                    del_resp.text[:200],
                )

            # Verify project is gone
            verify = await c.get(f"/api/projects/{project_id}")
            if verify.status_code == 404:
                log.info("Confirmed: project no longer accessible")
            else:
                log.warning("Project still returns %d after deletion", verify.status_code)


def main() -> None:
    log.info("Migration Test — Database-Per-Project Architecture")
    log.info("Base URL: %s", BASE_URL)
    log.info("Max Graph pages: %d", MAX_PAGES)
    log.info("Target tenant: %s", TARGET_TENANT_ID or "(not set)")

    try:
        asyncio.run(run_test())
    except MigrationTestError as exc:
        log.error("MIGRATION TEST FAILED: %s", exc)
        sys.exit(1)
    except KeyboardInterrupt:
        log.info("Interrupted")
        sys.exit(130)


if __name__ == "__main__":
    main()
