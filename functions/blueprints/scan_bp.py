"""Main scan orchestrator, HTTP trigger, and scan-state activities."""

from __future__ import annotations

import json
import logging
from typing import Any

import azure.durable_functions as df
import azure.functions as func

from blueprints.shared import RETRY_OPTIONS, cosmos_config
from utils.cosmos_writer import cleanup_scan_staging
from utils.scan_state import finalize_scan, update_scan_phase

logger = logging.getLogger(__name__)

bp = df.Blueprint()

_IDENTITY_BATCH_SIZE = 50


# ------------------------------------------------------------------
# HTTP trigger — start a scan orchestration
# ------------------------------------------------------------------

@bp.route(route="start_scan", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
@bp.durable_client_input(client_name="client")
async def start_scan(req: func.HttpRequest, client) -> func.HttpResponse:
    """Validate input and start the main scan orchestrator."""
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json",
        )

    required = ["tenant_id", "client_id", "client_secret", "project_id", "scan_id",
                 "cosmos_endpoint", "cosmos_key", "cosmos_database"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return func.HttpResponse(
            json.dumps({"error": f"Missing fields: {', '.join(missing)}"}),
            status_code=400,
            mimetype="application/json",
        )

    instance_id = await client.start_new("orchestrate_scan", client_input=body)

    return client.create_check_status_response(req, instance_id)


# ------------------------------------------------------------------
# Main orchestrator — fan-out across phases
# ------------------------------------------------------------------

@bp.orchestration_trigger(context_name="context")
def orchestrate_scan(context: df.DurableOrchestrationContext):
    payload: dict[str, Any] = context.get_input()
    project_id = payload["project_id"]
    scan_id = payload["scan_id"]

    # ---- Phase 1: mark scan running ----
    context.set_custom_status({"step": "starting", "message": "Scan starting..."})
    yield context.call_activity("update_scan_phase_activity", {
        **payload, "phase_name": "audit_logs", "phase_status": "running",
        "items_processed": 0,
    })
    yield context.call_activity("update_scan_phase_activity", {
        **payload, "phase_name": "sign_in_logs", "phase_status": "running",
        "items_processed": 0,
    })

    # ---- Phase 2: audit_logs + sign_in_logs in parallel ----
    context.set_custom_status({"step": "log_collection", "message": "Fetching audit + sign-in logs in parallel..."})

    log_tasks = [
        context.call_sub_orchestrator("orchestrate_audit_logs", payload, instance_id=f"{scan_id}_audit"),
        context.call_sub_orchestrator("orchestrate_sign_in_logs", payload, instance_id=f"{scan_id}_signin"),
    ]
    log_results = yield context.task_all(log_tasks)
    audit_result, signin_result = log_results

    # Check for errors
    errors = []
    if audit_result.get("error"):
        errors.append(f"audit_logs: {audit_result['error']}")
    if signin_result.get("error"):
        errors.append(f"sign_in_logs: {signin_result['error']}")

    if errors:
        yield context.call_activity("finalize_scan_activity", {
            **payload, "status": "failed",
            "error_message": "; ".join(errors),
        })
        context.set_custom_status({"step": "failed", "message": "; ".join(errors)})
        return {"status": "failed", "errors": errors}

    # Collect actor entries from both log phases
    all_actor_entries: list[list[str]] = []
    all_actor_entries.extend(audit_result.get("actor_entries", []))
    all_actor_entries.extend(signin_result.get("actor_entries", []))

    # Deduplicate actors by identity_id
    seen: set[str] = set()
    unique_actors: list[list[str]] = []
    for entry in all_actor_entries:
        if entry[0] not in seen:
            seen.add(entry[0])
            unique_actors.append(entry)

    total_events = audit_result.get("count", 0) + signin_result.get("count", 0)
    context.set_custom_status({
        "step": "log_collection_done",
        "message": f"Log collection done: {total_events} events, {len(unique_actors)} identities.",
        "total_events": total_events,
        "identity_count": len(unique_actors),
    })

    # ---- Phase 3: directory data in parallel (users, SPs, roles) ----
    context.set_custom_status({"step": "directory_data", "message": "Fetching users, service principals, role assignments..."})

    yield context.call_activity("update_scan_phase_activity", {
        **payload, "phase_name": "role_assignments", "phase_status": "running",
        "items_processed": 0,
    })

    dir_tasks = [
        context.call_sub_orchestrator("orchestrate_users", payload, instance_id=f"{scan_id}_users"),
        context.call_sub_orchestrator("orchestrate_service_principals", payload, instance_id=f"{scan_id}_sps"),
        context.call_sub_orchestrator("orchestrate_role_assignments", payload, instance_id=f"{scan_id}_roles"),
    ]
    dir_results = yield context.task_all(dir_tasks)
    users_result, sps_result, roles_result = dir_results

    dir_errors = []
    for name, res in [("users", users_result), ("service_principals", sps_result), ("role_assignments", roles_result)]:
        if res.get("error"):
            dir_errors.append(f"{name}: {res['error']}")

    if dir_errors:
        yield context.call_activity("finalize_scan_activity", {
            **payload, "status": "failed",
            "error_message": "; ".join(dir_errors),
        })
        context.set_custom_status({"step": "failed", "message": "; ".join(dir_errors)})
        return {"status": "failed", "errors": dir_errors}

    yield context.call_activity("update_scan_phase_activity", {
        **payload, "phase_name": "role_assignments", "phase_status": "completed",
        "items_processed": roles_result.get("count", 0),
    })

    context.set_custom_status({
        "step": "directory_data_done",
        "message": f"Directory data done: {users_result.get('count', 0)} users, {sps_result.get('count', 0)} SPs, {roles_result.get('count', 0)} role assignments.",
    })

    # ---- Phase 4: identity profile batches in parallel ----
    context.set_custom_status({
        "step": "identity_profiles",
        "message": f"Building {len(unique_actors)} identity profiles...",
    })
    yield context.call_activity("update_scan_phase_activity", {
        **payload, "phase_name": "identity_profiles", "phase_status": "running",
        "items_processed": 0,
    })

    batches = [
        unique_actors[i : i + _IDENTITY_BATCH_SIZE]
        for i in range(0, len(unique_actors), _IDENTITY_BATCH_SIZE)
    ]

    if batches:
        batch_tasks = [
            context.call_activity_with_retry(
                "process_identity_batch_activity",
                RETRY_OPTIONS,
                {**payload, "actor_entries": batch},
            )
            for batch in batches
        ]
        batch_results = yield context.task_all(batch_tasks)
        total_processed = sum(r.get("processed", 0) for r in batch_results)
        total_errors = sum(r.get("errors", 0) for r in batch_results)
    else:
        total_processed = 0
        total_errors = 0

    yield context.call_activity("update_scan_phase_activity", {
        **payload, "phase_name": "identity_profiles", "phase_status": "completed",
        "items_processed": total_processed,
    })

    # ---- Phase 5: finalize ----
    context.set_custom_status({"step": "finalizing", "message": "Finalizing scan..."})

    yield context.call_activity("finalize_scan_activity", {
        **payload, "status": "completed",
        "summary": {
            "total_events": total_events,
            "identities_processed": total_processed,
            "identity_errors": total_errors,
            "audit_events": audit_result.get("count", 0),
            "sign_in_events": signin_result.get("count", 0),
            "users_fetched": users_result.get("count", 0),
            "sps_fetched": sps_result.get("count", 0),
            "role_assignments_fetched": roles_result.get("count", 0),
        },
    })

    context.set_custom_status({
        "step": "completed",
        "message": f"Scan complete: {total_events} events, {total_processed} identities.",
        "total_events": total_events,
        "identities_processed": total_processed,
    })

    return {
        "status": "completed",
        "total_events": total_events,
        "identities_processed": total_processed,
    }


# ------------------------------------------------------------------
# Activities: scan state management
# ------------------------------------------------------------------

@bp.activity_trigger(input_name="payload")
def update_scan_phase_activity(payload: dict) -> None:
    """Update a scan phase in Cosmos DB."""
    cfg = cosmos_config(payload)
    phase_name = payload["phase_name"]
    phase_status = payload["phase_status"]
    items = payload.get("items_processed", 0)
    logger.info(
        "update_scan_phase | scan=%s | phase=%s | status=%s | items=%d",
        payload.get("scan_id", "?"), phase_name, phase_status, items,
    )
    update_scan_phase(
        cfg["endpoint"], cfg["key"], cfg["database"],
        payload["project_id"], payload["scan_id"],
        phase_name, phase_status,
        items_processed=items,
    )


@bp.activity_trigger(input_name="payload")
def finalize_scan_activity(payload: dict) -> None:
    """Finalize a scan (completed or failed) and clean up staging."""
    scan_id = payload.get("scan_id", "?")
    final_status = payload["status"]
    logger.info(
        "finalize_scan START | scan=%s | status=%s",
        scan_id, final_status,
    )
    cfg = cosmos_config(payload)
    finalize_scan(
        cfg["endpoint"], cfg["key"], cfg["database"],
        payload["project_id"], scan_id,
        final_status,
        summary=payload.get("summary"),
        error_message=payload.get("error_message"),
    )
    deleted = cleanup_scan_staging(
        cfg["endpoint"], cfg["key"], cfg["database"],
        scan_id,
    )
    logger.info(
        "finalize_scan DONE | scan=%s | status=%s | staging_docs_deleted=%d",
        scan_id, final_status, deleted,
    )
