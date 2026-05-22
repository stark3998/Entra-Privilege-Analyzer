"""Audit log sub-orchestrator and page-fetch activity."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import azure.durable_functions as df

from blueprints.shared import RETRY_OPTIONS, cosmos_config
from utils.event_parser import parse_audit_event
from utils.graph_auth import acquire_graph_token
from utils.graph_client import graph_get
from utils.cosmos_writer import upsert_action_events
from utils.log_context import set_scan_context
from utils.scan_state import update_scan_phase

logger = logging.getLogger(__name__)

bp = df.Blueprint()


@bp.orchestration_trigger(context_name="context")
def orchestrate_audit_logs(context: df.DurableOrchestrationContext):
    payload: dict[str, Any] = context.get_input()

    page = 0
    total = payload.get("resume_items_processed", 0)
    next_link = payload.get("resume_next_link")
    all_actor_entries: list[list[str]] = []

    if next_link:
        context.set_custom_status({
            "step": "resuming_audit_logs",
            "message": f"Resuming audit logs from checkpoint ({total} events already collected)...",
            "count": total,
        })

    while True:
        context.set_custom_status({
            "step": "fetching_audit_logs",
            "message": f"Fetching audit logs — page {page + 1} ({total} events so far)...",
            "page": page + 1,
            "count": total,
        })
        page_input = {**payload, "next_link": next_link, "page_number": page}
        try:
            result = yield context.call_activity_with_retry(
                "fetch_audit_log_page_activity", RETRY_OPTIONS, page_input,
            )
        except Exception as exc:
            context.set_custom_status({
                "step": "failed",
                "message": f"Failed fetching audit logs on page {page + 1}: {exc}",
                "count": total,
            })
            return {"count": total, "actor_entries": all_actor_entries, "error": str(exc)}

        if result.get("error"):
            context.set_custom_status({
                "step": "failed",
                "message": f"Audit logs fetch failed: {result['error']}",
                "count": total,
            })
            return {"count": total, "actor_entries": all_actor_entries, "error": result["error"]}

        total += result["count"]
        all_actor_entries.extend(result.get("actor_entries", []))
        page += 1

        next_link = result.get("next_link")

        yield context.call_activity("update_scan_phase_activity", {
            **payload, "phase_name": "audit_logs", "phase_status": "running",
            "items_processed": total,
            "checkpoint_next_link": next_link,
        })

        if not next_link:
            break

    yield context.call_activity("update_scan_phase_activity", {
        **payload, "phase_name": "audit_logs", "phase_status": "completed",
        "items_processed": total,
    })

    context.set_custom_status({
        "step": "completed",
        "message": f"Audit logs complete: {total} events across {page} pages.",
        "count": total,
    })
    return {"count": total, "actor_entries": all_actor_entries}


@bp.activity_trigger(input_name="payload")
def fetch_audit_log_page_activity(payload: dict) -> dict:
    """Fetch one page of audit logs, parse events, store to Cosmos."""
    set_scan_context(payload)
    scan_id = payload.get("scan_id", "?")
    page_num = payload.get("page_number", 0)
    tenant_id = payload["tenant_id"]

    logger.info(
        "fetch_audit_log_page START | scan=%s | tenant=%s | page=%d",
        scan_id, tenant_id, page_num,
    )
    activity_start = time.monotonic()

    try:
        token = acquire_graph_token(
            tenant_id, payload["client_id"], payload["client_secret"],
        )
    except Exception as exc:
        logger.error(
            "fetch_audit_log_page FAILED (auth) | scan=%s | page=%d | error=%s",
            scan_id, page_num, exc,
        )
        return {"count": 0, "next_link": None, "actor_entries": [], "error": str(exc)}

    graph_version = payload.get("graph_api_version", "beta")
    next_link = payload.get("next_link")

    try:
        if next_link:
            data = graph_get(token, next_link)
        else:
            since = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            url = f"https://graph.microsoft.com/{graph_version}/auditLogs/directoryAudits"
            data = graph_get(token, url, {"$filter": f"activityDateTime ge {since}", "$top": "999"})
    except Exception as exc:
        logger.error(
            "fetch_audit_log_page FAILED (graph) | scan=%s | page=%d | error=%s",
            scan_id, page_num, exc,
        )
        return {"count": 0, "next_link": None, "actor_entries": [], "error": str(exc)}

    page_items = data.get("value", [])
    events: list[dict[str, Any]] = []
    actor_entries: list[list[str]] = []

    for raw in page_items:
        event_dict, actor_id, actor_name = parse_audit_event(tenant_id, raw)
        events.append(event_dict)
        if actor_id != "unknown":
            actor_entries.append([event_dict["identity_id"], actor_name])

    if events:
        cfg = cosmos_config(payload)
        written = upsert_action_events(cfg["endpoint"], cfg["key"], cfg["database"], tenant_id, events)
        logger.info(
            "fetch_audit_log_page cosmos upsert | scan=%s | page=%d | written=%d/%d",
            scan_id, page_num, written, len(events),
        )

    elapsed_ms = (time.monotonic() - activity_start) * 1000
    has_next = data.get("@odata.nextLink") is not None
    logger.info(
        "fetch_audit_log_page DONE | scan=%s | page=%d | items=%d | actors=%d | has_next=%s | elapsed=%.0fms",
        scan_id, page_num, len(page_items), len(actor_entries), has_next, elapsed_ms,
    )

    return {
        "count": len(page_items),
        "next_link": data.get("@odata.nextLink"),
        "actor_entries": actor_entries,
    }
