"""Directory data sub-orchestrators and page-fetch activities.

Handles users, service principals, and role assignments (including PIM
schedule instances).  Data is stored to the scan_staging container so the
identity-profiles phase can read it without bloating orchestrator history.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import azure.durable_functions as df

from blueprints.shared import RETRY_OPTIONS, cosmos_config
from utils.graph_auth import acquire_graph_token
from utils.graph_client import graph_get
from utils.cosmos_writer import write_scan_staging
from utils.scan_state import update_scan_phase

logger = logging.getLogger(__name__)

bp = df.Blueprint()


# ------------------------------------------------------------------
# Users sub-orchestrator
# ------------------------------------------------------------------

@bp.orchestration_trigger(context_name="context")
def orchestrate_users(context: df.DurableOrchestrationContext):
    payload: dict[str, Any] = context.get_input()

    page = 0
    total = 0
    next_link = None

    while True:
        context.set_custom_status({
            "step": "fetching_users",
            "message": f"Fetching users — page {page + 1} ({total} so far)...",
            "page": page + 1,
            "count": total,
        })
        page_input = {**payload, "next_link": next_link, "page_number": page}
        try:
            result = yield context.call_activity_with_retry(
                "fetch_users_page_activity", RETRY_OPTIONS, page_input,
            )
        except Exception as exc:
            context.set_custom_status({
                "step": "failed",
                "message": f"Failed fetching users on page {page + 1}: {exc}",
                "count": total,
            })
            return {"count": total, "error": str(exc)}

        if result.get("error"):
            context.set_custom_status({
                "step": "failed",
                "message": f"Users fetch failed: {result['error']}",
                "count": total,
            })
            return {"count": total, "error": result["error"]}

        total += result["count"]
        page += 1

        next_link = result.get("next_link")
        if not next_link:
            break

    context.set_custom_status({
        "step": "completed",
        "message": f"Users complete: {total} across {page} pages.",
        "count": total,
    })
    return {"count": total}


# ------------------------------------------------------------------
# Service Principals sub-orchestrator
# ------------------------------------------------------------------

@bp.orchestration_trigger(context_name="context")
def orchestrate_service_principals(context: df.DurableOrchestrationContext):
    payload: dict[str, Any] = context.get_input()

    page = 0
    total = 0
    next_link = None

    while True:
        context.set_custom_status({
            "step": "fetching_service_principals",
            "message": f"Fetching service principals — page {page + 1} ({total} so far)...",
            "page": page + 1,
            "count": total,
        })
        page_input = {**payload, "next_link": next_link, "page_number": page}
        try:
            result = yield context.call_activity_with_retry(
                "fetch_sps_page_activity", RETRY_OPTIONS, page_input,
            )
        except Exception as exc:
            context.set_custom_status({
                "step": "failed",
                "message": f"Failed fetching SPs on page {page + 1}: {exc}",
                "count": total,
            })
            return {"count": total, "error": str(exc)}

        if result.get("error"):
            context.set_custom_status({
                "step": "failed",
                "message": f"SPs fetch failed: {result['error']}",
                "count": total,
            })
            return {"count": total, "error": result["error"]}

        total += result["count"]
        page += 1

        next_link = result.get("next_link")
        if not next_link:
            break

    context.set_custom_status({
        "step": "completed",
        "message": f"Service principals complete: {total} across {page} pages.",
        "count": total,
    })
    return {"count": total}


# ------------------------------------------------------------------
# Role Assignments activity (not paginated — single activity fetch)
# ------------------------------------------------------------------

@bp.orchestration_trigger(context_name="context")
def orchestrate_role_assignments(context: df.DurableOrchestrationContext):
    payload: dict[str, Any] = context.get_input()

    context.set_custom_status({
        "step": "fetching_role_assignments",
        "message": "Fetching role definitions and assignments...",
    })

    try:
        result = yield context.call_activity_with_retry(
            "fetch_role_assignments_activity", RETRY_OPTIONS, payload,
        )
    except Exception as exc:
        context.set_custom_status({
            "step": "failed",
            "message": f"Role assignments failed: {exc}",
        })
        return {"count": 0, "error": str(exc)}

    if result.get("error"):
        context.set_custom_status({
            "step": "failed",
            "message": f"Role assignments failed: {result['error']}",
        })
        return {"count": 0, "error": result["error"]}

    context.set_custom_status({
        "step": "completed",
        "message": f"Role assignments complete: {result['count']} assignments.",
        "count": result["count"],
    })
    return {"count": result["count"]}


# ------------------------------------------------------------------
# Activity: fetch one page of users → scan_staging
# ------------------------------------------------------------------

@bp.activity_trigger(input_name="payload")
def fetch_users_page_activity(payload: dict) -> dict:
    """Fetch one page of users, store raw JSON to scan_staging."""
    scan_id = payload.get("scan_id", "?")
    page_num = payload.get("page_number", 0)
    tenant_id = payload["tenant_id"]

    logger.info(
        "fetch_users_page START | scan=%s | tenant=%s | page=%d",
        scan_id, tenant_id, page_num,
    )
    activity_start = time.monotonic()

    try:
        token = acquire_graph_token(
            tenant_id, payload["client_id"], payload["client_secret"],
        )
    except Exception as exc:
        logger.error(
            "fetch_users_page FAILED (auth) | scan=%s | page=%d | error=%s",
            scan_id, page_num, exc,
        )
        return {"count": 0, "next_link": None, "error": str(exc)}

    graph_version = payload.get("graph_api_version", "beta")
    next_link = payload.get("next_link")

    try:
        if next_link:
            data = graph_get(token, next_link)
        else:
            url = f"https://graph.microsoft.com/{graph_version}/users"
            params = {
                "$select": (
                    "id,displayName,userPrincipalName,userType,accountEnabled,"
                    "creationType,externalUserState,externalUserStateChangeDateTime,"
                    "createdDateTime,signInActivity"
                ),
            }
            data = graph_get(token, url, params)
    except Exception as exc:
        logger.error(
            "fetch_users_page FAILED (graph) | scan=%s | page=%d | error=%s",
            scan_id, page_num, exc,
        )
        return {"count": 0, "next_link": None, "error": str(exc)}

    page_items = data.get("value", [])

    if page_items:
        cfg = cosmos_config(payload)
        write_scan_staging(
            cfg["endpoint"], cfg["key"], cfg["database"],
            payload["scan_id"], "users", page_items, page_num,
        )
        logger.info(
            "fetch_users_page staged | scan=%s | page=%d | items=%d",
            scan_id, page_num, len(page_items),
        )

    elapsed_ms = (time.monotonic() - activity_start) * 1000
    has_next = data.get("@odata.nextLink") is not None
    logger.info(
        "fetch_users_page DONE | scan=%s | page=%d | items=%d | has_next=%s | elapsed=%.0fms",
        scan_id, page_num, len(page_items), has_next, elapsed_ms,
    )

    return {
        "count": len(page_items),
        "next_link": data.get("@odata.nextLink"),
    }


# ------------------------------------------------------------------
# Activity: fetch one page of service principals → scan_staging
# ------------------------------------------------------------------

@bp.activity_trigger(input_name="payload")
def fetch_sps_page_activity(payload: dict) -> dict:
    """Fetch one page of service principals, store to scan_staging."""
    scan_id = payload.get("scan_id", "?")
    page_num = payload.get("page_number", 0)
    tenant_id = payload["tenant_id"]

    logger.info(
        "fetch_sps_page START | scan=%s | tenant=%s | page=%d",
        scan_id, tenant_id, page_num,
    )
    activity_start = time.monotonic()

    try:
        token = acquire_graph_token(
            tenant_id, payload["client_id"], payload["client_secret"],
        )
    except Exception as exc:
        logger.error(
            "fetch_sps_page FAILED (auth) | scan=%s | page=%d | error=%s",
            scan_id, page_num, exc,
        )
        return {"count": 0, "next_link": None, "error": str(exc)}

    graph_version = payload.get("graph_api_version", "beta")
    next_link = payload.get("next_link")

    try:
        if next_link:
            data = graph_get(token, next_link)
        else:
            url = f"https://graph.microsoft.com/{graph_version}/servicePrincipals"
            params = {
                "$select": (
                    "id,displayName,appId,servicePrincipalType,accountEnabled,"
                    "passwordCredentials,keyCredentials,createdDateTime"
                ),
            }
            data = graph_get(token, url, params)
    except Exception as exc:
        logger.error(
            "fetch_sps_page FAILED (graph) | scan=%s | page=%d | error=%s",
            scan_id, page_num, exc,
        )
        return {"count": 0, "next_link": None, "error": str(exc)}

    page_items = data.get("value", [])

    if page_items:
        cfg = cosmos_config(payload)
        write_scan_staging(
            cfg["endpoint"], cfg["key"], cfg["database"],
            payload["scan_id"], "service_principals", page_items, page_num,
        )
        logger.info(
            "fetch_sps_page staged | scan=%s | page=%d | items=%d",
            scan_id, page_num, len(page_items),
        )

    elapsed_ms = (time.monotonic() - activity_start) * 1000
    has_next = data.get("@odata.nextLink") is not None
    logger.info(
        "fetch_sps_page DONE | scan=%s | page=%d | items=%d | has_next=%s | elapsed=%.0fms",
        scan_id, page_num, len(page_items), has_next, elapsed_ms,
    )

    return {
        "count": len(page_items),
        "next_link": data.get("@odata.nextLink"),
    }


# ------------------------------------------------------------------
# Activity: fetch all role data (definitions + assignments + PIM)
# ------------------------------------------------------------------

@bp.activity_trigger(input_name="payload")
def fetch_role_assignments_activity(payload: dict) -> dict:
    """Fetch role definitions, active assignments, and PIM eligibilities.

    Stores three staging documents:
    - role_definitions: all directory role definitions
    - role_assignments: active role assignments (PIM schedule instances or legacy)
    - role_eligibilities: PIM-eligible role assignments
    """
    scan_id = payload.get("scan_id", "?")
    tenant_id = payload["tenant_id"]

    logger.info(
        "fetch_role_assignments START | scan=%s | tenant=%s",
        scan_id, tenant_id,
    )
    activity_start = time.monotonic()

    try:
        token = acquire_graph_token(
            tenant_id, payload["client_id"], payload["client_secret"],
        )
    except Exception as exc:
        logger.error(
            "fetch_role_assignments FAILED (auth) | scan=%s | error=%s",
            scan_id, exc,
        )
        return {"count": 0, "error": str(exc)}

    graph_version = payload.get("graph_api_version", "beta")
    base = f"https://graph.microsoft.com/{graph_version}"
    cfg = cosmos_config(payload)

    try:
        defs_data = _fetch_all_pages(token, f"{base}/roleManagement/directory/roleDefinitions")
        logger.info(
            "fetch_role_assignments definitions | scan=%s | count=%d",
            scan_id, len(defs_data),
        )
        write_scan_staging(
            cfg["endpoint"], cfg["key"], cfg["database"],
            scan_id, "role_definitions", defs_data,
        )

        try:
            assignments = _fetch_all_pages(
                token,
                f"{base}/roleManagement/directory/roleAssignmentScheduleInstances",
            )
            eligibilities = _fetch_all_pages(
                token,
                f"{base}/roleManagement/directory/roleEligibilityScheduleInstances",
            )
            logger.info(
                "fetch_role_assignments PIM APIs | scan=%s | assignments=%d | eligibilities=%d",
                scan_id, len(assignments), len(eligibilities),
            )
        except Exception as pim_exc:
            logger.warning(
                "PIM schedule APIs unavailable, falling back to roleAssignments | scan=%s | error=%s",
                scan_id, pim_exc,
            )
            assignments = _fetch_all_pages(
                token,
                f"{base}/roleManagement/directory/roleAssignments",
                params={"$expand": "principal,roleDefinition"},
            )
            eligibilities = []
            logger.info(
                "fetch_role_assignments legacy fallback | scan=%s | assignments=%d",
                scan_id, len(assignments),
            )

        write_scan_staging(
            cfg["endpoint"], cfg["key"], cfg["database"],
            scan_id, "role_assignments", assignments,
        )
        if eligibilities:
            write_scan_staging(
                cfg["endpoint"], cfg["key"], cfg["database"],
                scan_id, "role_eligibilities", eligibilities,
            )

    except Exception as exc:
        logger.error(
            "fetch_role_assignments FAILED | scan=%s | error=%s",
            scan_id, exc,
        )
        return {"count": 0, "error": str(exc)}

    elapsed_ms = (time.monotonic() - activity_start) * 1000
    total = len(assignments) + len(eligibilities)
    logger.info(
        "fetch_role_assignments DONE | scan=%s | definitions=%d | assignments=%d | eligibilities=%d | elapsed=%.0fms",
        scan_id, len(defs_data), len(assignments), len(eligibilities), elapsed_ms,
    )
    return {"count": total}


def _fetch_all_pages(
    token: str,
    url: str,
    params: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Follow @odata.nextLink to collect all pages into a single list."""
    all_items: list[dict[str, Any]] = []
    current_url: str | None = url
    current_params = params

    while current_url:
        data = graph_get(token, current_url, current_params)
        all_items.extend(data.get("value", []))
        current_url = data.get("@odata.nextLink")
        current_params = None

    return all_items
