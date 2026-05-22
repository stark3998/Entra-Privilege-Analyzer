"""Main scan orchestrator, HTTP trigger, and scan-state activities."""

from __future__ import annotations

import json
import logging
from typing import Any

import azure.durable_functions as df
import azure.functions as func

from blueprints.shared import RETRY_OPTIONS, cosmos_config
from utils.cosmos_writer import cleanup_scan_staging
from utils.log_context import set_scan_context
from utils.scan_state import finalize_scan, get_previous_scan_phases, update_scan_phase

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
    resume_from = payload.get("resume_from_scan_id")

    # ---- Load checkpoints from previous failed scan (if resuming) ----
    checkpoints: dict[str, dict] = {}
    if resume_from:
        context.set_custom_status({"step": "loading_checkpoint", "message": f"Loading checkpoints from scan {resume_from[:8]}..."})
        checkpoints = yield context.call_activity("load_checkpoint_activity", {
            **payload, "previous_scan_id": resume_from,
        })

    def _phase_completed(name: str) -> bool:
        return checkpoints.get(name, {}).get("status") == "completed"

    def _phase_checkpoint(name: str) -> str | None:
        return checkpoints.get(name, {}).get("checkpoint_next_link")

    def _phase_items(name: str) -> int:
        return checkpoints.get(name, {}).get("items_processed", 0)

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
    audit_checkpoint = _phase_checkpoint("audit_logs")
    signin_checkpoint = _phase_checkpoint("sign_in_logs")
    audit_prev_items = _phase_items("audit_logs")
    signin_prev_items = _phase_items("sign_in_logs")

    skip_audit = _phase_completed("audit_logs")
    skip_signin = _phase_completed("sign_in_logs")

    if skip_audit and skip_signin:
        context.set_custom_status({"step": "log_collection", "message": "Log phases already completed — skipping."})
        audit_result = {"count": audit_prev_items, "actor_entries": []}
        signin_result = {"count": signin_prev_items, "actor_entries": []}
    else:
        resume_suffix = ""
        if audit_checkpoint or signin_checkpoint:
            resume_suffix = " (resuming from checkpoint)"
        context.set_custom_status({"step": "log_collection", "message": f"Fetching audit + sign-in logs in parallel...{resume_suffix}"})

        log_tasks = []
        audit_idx = signin_idx = -1
        idx = 0

        if not skip_audit:
            audit_payload = {**payload}
            if audit_checkpoint:
                audit_payload["resume_next_link"] = audit_checkpoint
                audit_payload["resume_items_processed"] = audit_prev_items
            log_tasks.append(context.call_sub_orchestrator("orchestrate_audit_logs", audit_payload, instance_id=f"{scan_id}_audit"))
            audit_idx = idx
            idx += 1
        if not skip_signin:
            signin_payload = {**payload}
            if signin_checkpoint:
                signin_payload["resume_next_link"] = signin_checkpoint
                signin_payload["resume_items_processed"] = signin_prev_items
            log_tasks.append(context.call_sub_orchestrator("orchestrate_sign_in_logs", signin_payload, instance_id=f"{scan_id}_signin"))
            signin_idx = idx
            idx += 1

        log_results = yield context.task_all(log_tasks)

        audit_result = log_results[audit_idx] if audit_idx >= 0 else {"count": audit_prev_items, "actor_entries": []}
        signin_result = log_results[signin_idx] if signin_idx >= 0 else {"count": signin_prev_items, "actor_entries": []}

    if audit_result.get("error"):
        error_msg = f"audit_logs: {audit_result['error']}"
        yield context.call_activity("finalize_scan_activity", {
            **payload, "status": "failed",
            "error_message": error_msg,
        })
        context.set_custom_status({"step": "failed", "message": error_msg})
        return {"status": "failed", "errors": [error_msg]}

    warnings = []
    if signin_result.get("error"):
        warnings.append(f"sign_in_logs: {signin_result['error']} (collected {signin_result.get('count', 0)} events)")

    all_actor_entries: list[list[str]] = []
    all_actor_entries.extend(audit_result.get("actor_entries", []))
    all_actor_entries.extend(signin_result.get("actor_entries", []))

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

    summary = {
        "total_events": total_events,
        "identities_processed": total_processed,
        "identity_errors": total_errors,
        "audit_events": audit_result.get("count", 0),
        "sign_in_events": signin_result.get("count", 0),
        "users_fetched": users_result.get("count", 0),
        "sps_fetched": sps_result.get("count", 0),
        "role_assignments_fetched": roles_result.get("count", 0),
    }
    if warnings:
        summary["warnings"] = warnings

    yield context.call_activity("finalize_scan_activity", {
        **payload, "status": "completed",
        "summary": summary,
    })

    warn_suffix = f" (warnings: {len(warnings)})" if warnings else ""
    context.set_custom_status({
        "step": "completed",
        "message": f"Scan complete: {total_events} events, {total_processed} identities.{warn_suffix}",
        "total_events": total_events,
        "identities_processed": total_processed,
    })

    return {
        "status": "completed",
        "total_events": total_events,
        "identities_processed": total_processed,
        "warnings": warnings,
    }


# ------------------------------------------------------------------
# Activities: scan state management
# ------------------------------------------------------------------

@bp.activity_trigger(input_name="payload")
def update_scan_phase_activity(payload: dict) -> None:
    """Update a scan phase in Cosmos DB."""
    set_scan_context(payload)
    cfg = cosmos_config(payload)
    phase_name = payload["phase_name"]
    phase_status = payload["phase_status"]
    items = payload.get("items_processed", 0)
    checkpoint = payload.get("checkpoint_next_link")
    logger.info(
        "update_scan_phase | scan=%s | phase=%s | status=%s | items=%d | checkpoint=%s",
        payload.get("scan_id", "?"), phase_name, phase_status, items,
        "yes" if checkpoint else "no",
    )
    update_scan_phase(
        cfg["endpoint"], cfg["key"], cfg["master_database"],
        payload["project_id"], payload["scan_id"],
        phase_name, phase_status,
        items_processed=items,
        checkpoint_next_link=checkpoint,
    )


@bp.activity_trigger(input_name="payload")
def finalize_scan_activity(payload: dict) -> None:
    """Finalize a scan (completed or failed) and clean up staging."""
    set_scan_context(payload)
    scan_id = payload.get("scan_id", "?")
    final_status = payload["status"]
    logger.info(
        "finalize_scan START | scan=%s | status=%s",
        scan_id, final_status,
    )
    cfg = cosmos_config(payload)
    finalize_scan(
        cfg["endpoint"], cfg["key"], cfg["master_database"],
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


@bp.activity_trigger(input_name="payload")
def load_checkpoint_activity(payload: dict) -> dict:
    """Load phase checkpoints from a previous (failed) scan."""
    set_scan_context(payload)
    cfg = cosmos_config(payload)
    previous_scan_id = payload["previous_scan_id"]
    logger.info(
        "load_checkpoint | scan=%s | loading phases from previous=%s",
        payload.get("scan_id", "?"), previous_scan_id,
    )
    phases = get_previous_scan_phases(
        cfg["endpoint"], cfg["key"], cfg["master_database"],
        payload["project_id"], previous_scan_id,
    )
    checkpoints: dict[str, dict] = {}
    for phase in phases:
        checkpoints[phase["name"]] = {
            "status": phase.get("status", "pending"),
            "items_processed": phase.get("items_processed", 0),
            "checkpoint_next_link": phase.get("checkpoint_next_link"),
        }
    logger.info(
        "load_checkpoint | previous=%s | phases=%s",
        previous_scan_id,
        {k: v["status"] for k, v in checkpoints.items()},
    )
    return checkpoints
