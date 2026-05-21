#!/usr/bin/env python3
"""Run an end-to-end scan validation against the local backend API.

This script:
1) Loads credentials/config from a .env file.
2) Creates a project with app credentials.
3) Triggers a full scan and polls until terminal state.
4) Verifies scan/log/data endpoints backed by Cosmos DB.
5) Runs analysis endpoints and verifies outputs.

Exit codes:
- 0: All checks passed
- 1: Validation failed
- 2: Configuration error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ApiResponse:
    status: int
    text: str
    data: Any | None


class ApiClient:
    def __init__(self, base_url: str, timeout: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> ApiResponse:
        url = f"{self.base_url}{path}"
        body_bytes = None
        headers: dict[str, str] = {}

        if payload is not None:
            body_bytes = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url=url, data=body_bytes, method=method.upper(), headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                return ApiResponse(status=resp.status, text=text, data=_safe_json(text))
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", errors="replace") if e.fp else ""
            return ApiResponse(status=e.code, text=text, data=_safe_json(text))


def _safe_json(text: str) -> Any | None:
    if not text or not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith(('"', "'")) and value.endswith(('"', "'")) and len(value) >= 2:
            value = value[1:-1]
        out[key] = value
    return out


def env_get(env: dict[str, str], *keys: str) -> str:
    for key in keys:
        val = env.get(key, "").strip()
        if val:
            return val
    return ""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{now_iso()}] {msg}", flush=True)


def extract_scan_id(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    for key in ("scan_id", "id"):
        v = data.get(key)
        if isinstance(v, str) and v:
            return v
    scan = data.get("scan")
    if isinstance(scan, dict):
        for key in ("scan_id", "id"):
            v = scan.get(key)
            if isinstance(v, str) and v:
                return v
    return ""


def extract_items_count(data: Any) -> int:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list):
            return len(items)
        if "id" in data:
            return 1
    return 0


def terminal_status(status: str) -> bool:
    return status in {"completed", "failed", "cancelled", "terminated"}


def status_of_scan(data: Any) -> str:
    if isinstance(data, dict):
        if isinstance(data.get("status"), str):
            return data["status"].lower()
        scan = data.get("scan")
        if isinstance(scan, dict) and isinstance(scan.get("status"), str):
            return scan["status"].lower()
    return "unknown"


def phases_of_scan(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("phases"), list):
        return [p for p in data["phases"] if isinstance(p, dict)]
    scan = data.get("scan")
    if isinstance(scan, dict) and isinstance(scan.get("phases"), list):
        return [p for p in scan["phases"] if isinstance(p, dict)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate full E2E scan and analysis workflow.")
    parser.add_argument("--env-file", default=".env", help="Path to .env file (default: .env)")
    parser.add_argument("--base-url", default="", help="Backend API base URL override")
    parser.add_argument("--poll-seconds", type=int, default=10, help="Scan polling interval in seconds")
    parser.add_argument("--timeout-minutes", type=int, default=20, help="Max scan wait time in minutes")
    args = parser.parse_args()

    env_path = Path(args.env_file).resolve()
    env = load_env_file(env_path)

    base_url = (
        args.base_url.strip()
        or env_get(env, "API_BASE_URL", "VITE_API_BASE_URL")
        or "http://localhost:8000"
    )
    base_url = base_url.rstrip("/")

    tenant_id = env_get(env, "GRAPH_APP_TENANT_ID", "AZURE_TENANT_ID")
    tenant_name = env_get(env, "GRAPH_APP_TENANT_NAME") or "Local Tenant"
    client_id = env_get(env, "GRAPH_APP_CLIENT_ID", "AZURE_CLIENT_ID")
    client_secret = env_get(env, "GRAPH_APP_CLIENT_SECRET", "AZURE_CLIENT_SECRET")

    if not tenant_id or not client_id or not client_secret:
        log("CONFIG FAIL: Missing tenant/client credentials in env file")
        log("Expected GRAPH_APP_* (preferred) or AZURE_CLIENT_* + AZURE_TENANT_ID")
        return 2

    log(f"Using env file: {env_path}")
    log(f"Base URL: {base_url}")
    log(f"Tenant ID: {tenant_id}")
    log(f"Client ID: {client_id}")

    api = ApiClient(base_url)

    # 1) Health
    health = api.request("GET", "/healthz")
    log(f"healthz => {health.status}")
    if health.status != 200:
        log(f"FAIL healthz response: {health.text}")
        return 1

    # 2) Create project with credentials
    project_name = f"E2E Scan Validation {datetime.now().strftime('%Y%m%d-%H%M%S')}"
    payload = {
        "name": project_name,
        "target_tenant_id": tenant_id,
        "target_tenant_name": tenant_name,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    create = api.request("POST", "/api/projects", payload)
    log(f"create project => {create.status}")
    if create.status not in (200, 201):
        log(f"FAIL project creation: {create.text}")
        return 1

    if not isinstance(create.data, dict):
        log("FAIL project creation response was not JSON object")
        return 1

    project_id = str(create.data.get("id", "")).strip()
    if not project_id:
        log(f"FAIL could not extract project id from create response: {create.text}")
        return 1

    log(f"Project created: {project_id}")

    # 3) Trigger full scan
    trigger = api.request("POST", f"/api/projects/{urllib.parse.quote(project_id)}/scans/trigger?full=true")
    log(f"trigger full scan => {trigger.status}")
    if trigger.status != 202:
        log(f"FAIL scan trigger: {trigger.text}")
        return 1

    scan_id = extract_scan_id(trigger.data)
    if not scan_id:
        log(f"FAIL could not extract scan id from trigger response: {trigger.text}")
        return 1
    log(f"Scan ID: {scan_id}")

    # 4) Poll latest scan
    deadline = time.time() + (args.timeout_minutes * 60)
    latest_data: Any = None
    final_status = "unknown"

    while time.time() < deadline:
        latest = api.request("GET", f"/api/projects/{urllib.parse.quote(project_id)}/scans/latest")
        if latest.status != 200:
            log(f"WARN latest scan request => {latest.status}")
            time.sleep(args.poll_seconds)
            continue

        latest_data = latest.data
        final_status = status_of_scan(latest_data)

        phase_chunks: list[str] = []
        for ph in phases_of_scan(latest_data):
            name = str(ph.get("name", "phase"))
            status = str(ph.get("status", "unknown"))
            items = ph.get("items_processed", "-")
            phase_chunks.append(f"{name}:{status}({items})")

        phase_summary = ", ".join(phase_chunks) if phase_chunks else "no-phases"
        log(f"poll status={final_status} phases=[{phase_summary}]")

        if terminal_status(final_status):
            break
        time.sleep(args.poll_seconds)

    if not terminal_status(final_status):
        log(f"FAIL scan timeout after {args.timeout_minutes} minutes")
        return 1

    # 5) Check scan logs endpoint regardless of status.
    scan_logs = api.request("GET", f"/api/projects/{urllib.parse.quote(project_id)}/scans/{urllib.parse.quote(scan_id)}/logs")
    logs_ok = scan_logs.status == 200
    log(f"scan logs => {scan_logs.status}")

    if final_status != "completed":
        err_msg = ""
        if isinstance(latest_data, dict):
            err_msg = str(latest_data.get("error_message", "")).strip()
            if not err_msg and isinstance(latest_data.get("scan"), dict):
                err_msg = str(latest_data["scan"].get("error_message", "")).strip()
        log(f"FAIL scan status={final_status} error={err_msg or '<none>'}")
        return 1

    # 6) Validate data endpoints (Cosmos-backed)
    analytics = api.request("GET", f"/api/projects/{urllib.parse.quote(project_id)}/analytics")
    identities = api.request("GET", f"/api/projects/{urllib.parse.quote(project_id)}/identities")
    drift_before = api.request("GET", f"/api/projects/{urllib.parse.quote(project_id)}/drift-alerts")

    log(f"analytics => {analytics.status}")
    log(f"identities => {identities.status}")
    log(f"drift-alerts (before detect) => {drift_before.status}")

    stored_in_cosmos_ok = analytics.status == 200 and identities.status == 200 and drift_before.status == 200

    identities_count = extract_items_count(identities.data)

    # 7) Run analysis endpoints
    reco_compute = api.request("POST", f"/api/projects/{urllib.parse.quote(project_id)}/recommendations/compute")
    bp_eval = api.request("POST", f"/api/projects/{urllib.parse.quote(project_id)}/best-practices/evaluate")
    drift_detect = api.request("POST", f"/api/projects/{urllib.parse.quote(project_id)}/drift-alerts/detect")

    log(f"recommendations/compute => {reco_compute.status}")
    log(f"best-practices/evaluate => {bp_eval.status}")
    log(f"drift-alerts/detect => {drift_detect.status}")

    time.sleep(20)

    reco_list = api.request("GET", f"/api/projects/{urllib.parse.quote(project_id)}/recommendations")
    bp_summary = api.request("GET", f"/api/projects/{urllib.parse.quote(project_id)}/best-practices/summary")
    drift_after = api.request("GET", f"/api/projects/{urllib.parse.quote(project_id)}/drift-alerts")

    log(f"recommendations => {reco_list.status}")
    log(f"best-practices/summary => {bp_summary.status}")
    log(f"drift-alerts (after detect) => {drift_after.status}")

    analysis_ok = all(
        s in (200, 201, 202)
        for s in (reco_compute.status, bp_eval.status, drift_detect.status)
    ) and all(
        s == 200 for s in (reco_list.status, bp_summary.status, drift_after.status)
    )

    reco_count = extract_items_count(reco_list.data)
    drift_count = extract_items_count(drift_after.data)

    bp_total = ""
    bp_score = ""
    if isinstance(bp_summary.data, dict):
        bp_total = str(bp_summary.data.get("total_violations", ""))
        bp_score = str(bp_summary.data.get("compliance_score", ""))

    # 8) Final report and exit
    print("\n=== E2E VALIDATION REPORT ===")
    print(f"project_id={project_id}")
    print(f"project_name={project_name}")
    print(f"scan_id={scan_id}")
    print(f"scan_status={final_status}")
    print(f"identities_count={identities_count}")
    print(f"recommendations_count={reco_count}")
    print(f"drift_alerts_count={drift_count}")
    print(f"best_practices_total_violations={bp_total}")
    print(f"best_practices_compliance_score={bp_score}")
    print(f"PASS_graph_and_scan={('YES' if final_status == 'completed' else 'NO')}")
    print(f"PASS_logs_endpoint={('YES' if logs_ok else 'NO')}")
    print(f"PASS_stored_in_cosmos={('YES' if stored_in_cosmos_ok else 'NO')}")
    print(f"PASS_analysis_completed={('YES' if analysis_ok else 'NO')}")

    if final_status == "completed" and logs_ok and stored_in_cosmos_ok and analysis_ok:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
