"""Data Reliability Command Center — Web Server & API Backend.

Provides REST API endpoints for metrics, contracts, history, lineage,
and live script execution (reset, inject faults, run baseline, pytest).
Includes full server-side trace logging and CORS preflight support.
"""
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.contract_validator import load_contract

STATIC_DIR = Path(__file__).resolve().parent / "static"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = Path(sys.executable)

# Action execution lock to prevent overlapping runs
ACTION_LOCK = threading.Lock()
LAST_ACTION_LOG: dict[str, Any] = {
    "action": "none",
    "status": "idle",
    "output": "Ready to execute operations.",
    "timestamp": None,
}


def log_server_event(tag: str, msg: str, color_code: str = "\033[94m") -> None:
    """Format and print structured server trace log."""
    now = datetime.now().strftime("%H:%M:%S")
    reset = "\033[0m"
    print(f"[{now}] {color_code}[{tag}]{reset} {msg}", flush=True)


def run_subcommand(command: list[str]) -> tuple[int, str]:
    """Execute a python/pytest command in the repository workspace with full tracing."""
    cmd_str = " ".join(command)
    log_server_event("CMD-START", f"Executing: {cmd_str}", "\033[93m")
    start_t = time.perf_counter()
    trace_prefix = f"$ {cmd_str}\n"
    try:
        proc = subprocess.run(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.perf_counter() - start_t
        tag = "CMD-SUCCESS" if proc.returncode == 0 else "CMD-FAIL"
        color = "\033[92m" if proc.returncode == 0 else "\033[91m"
        log_server_event(tag, f"Finished in {elapsed:.2f}s (code={proc.returncode})", color)
        if proc.stdout.strip():
            # Print brief preview of output to terminal
            lines = proc.stdout.strip().splitlines()
            for line in lines[:8]:
                print(f"    | {line}", flush=True)
            if len(lines) > 8:
                print(f"    | ... ({len(lines) - 8} more lines)", flush=True)
        trace_suffix = f"\n[command_exit_code={proc.returncode}; elapsed={elapsed:.2f}s]"
        return proc.returncode, trace_prefix + (proc.stdout or "") + trace_suffix
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - start_t
        log_server_event("CMD-TIMEOUT", f"Execution timed out after {elapsed:.2f}s", "\033[91m")
        return 1, trace_prefix + "Command timed out after 60 seconds.\n[command_exit_code=1]"
    except Exception as e:
        elapsed = time.perf_counter() - start_t
        log_server_event("CMD-ERROR", f"Execution failed: {e}", "\033[91m")
        return 1, trace_prefix + f"Execution failed: {e}\n[command_exit_code=1]"


def get_latest_metrics() -> dict[str, Any]:
    report_file = ROOT / "reports" / "latest_metrics.json"
    if report_file.exists():
        try:
            return json.loads(report_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "timestamp": None,
        "orders_rows": 0,
        "failed_contract_checks": 0,
        "critical_contract_failures": 0,
        "kb_failed_checks": 0,
        "freshness_minutes": 0,
        "row_count_anomaly": {"is_anomaly": False, "score": 0.0, "method": "none"},
        "kb_text_length_signal": {"is_anomaly": False, "score": 0.0, "current_mean": 0},
        "contract_slo": {
            "target": 0.999,
            "actual_bad_rate": 0.0,
            "allowed_bad_rate": 0.001,
            "burn_rate": 0.0,
            "remaining_error_budget_fraction": 1.0,
            "breached": False,
        },
        "sample_blast_radius_from_stg_orders": [],
    }


def get_history_data() -> list[dict[str, Any]]:
    history_file = ROOT / "data" / "history" / "metrics_history.csv"
    if not history_file.exists():
        return []
    try:
        import pandas as pd

        df = pd.read_csv(history_file)
        return df.to_dict(orient="records")
    except Exception:
        return []


def get_lineage_data() -> dict[str, Any]:
    lineage_file = ROOT / "data" / "baseline" / "lineage_graph.json"
    if lineage_file.exists():
        try:
            return json.loads(lineage_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"dataset_lineage": {}, "column_lineage": {}}


def get_contract_files() -> dict[str, Any]:
    orders_contract = ROOT / "contracts" / "orders_contract.yaml"
    kb_contract = ROOT / "contracts" / "kb_contract.yaml"
    res: dict[str, Any] = {}
    if orders_contract.exists():
        res["orders_contract"] = orders_contract.read_text(encoding="utf-8")
        orders = load_contract(orders_contract)
        res["orders_rules"] = _contract_rule_rows(orders)
        res["orders_freshness_max_delay_minutes"] = orders.get("freshness", {}).get("max_delay_minutes")
    if kb_contract.exists():
        res["kb_contract"] = kb_contract.read_text(encoding="utf-8")
        kb = load_contract(kb_contract)
        res["kb_rules"] = _contract_rule_rows(kb)
        res["kb_freshness_max_delay_minutes"] = kb.get("freshness", {}).get("max_delay_minutes")
    return res


def _contract_rule_rows(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize either columns/fields contract syntax for the UI."""
    rows: list[dict[str, Any]] = []
    freshness = contract.get("freshness", {})
    if freshness:
        rows.append({
            "field": freshness.get("column", "freshness"),
            "type": "datetime",
            "constraints": f"max_delay: {freshness.get('max_delay_minutes')} mins",
            "severity": freshness.get("severity", "warning"),
            "check": "freshness",
        })
    fields = contract.get("columns") or contract.get("fields") or {}
    for field, rules in fields.items():
        constraints: list[str] = []
        if rules.get("required"):
            constraints.append("not_null")
        if rules.get("unique"):
            constraints.append("unique")
        if "min" in rules:
            constraints.append(f"min: {rules['min']}")
        if "max" in rules:
            constraints.append(f"max: {rules['max']}")
        if "min_length" in rules:
            constraints.append(f"min_length: {rules['min_length']}")
        if "accepted_values" in rules:
            constraints.append(f"accepted: {rules['accepted_values']}")
        rows.append({
            "field": field,
            "type": rules.get("type", "unknown"),
            "constraints": ", ".join(constraints) or "—",
            "severity": rules.get("severity", "warning"),
            "check": field,
        })
    return rows


def _remote_actions_allowed(handler: SimpleHTTPRequestHandler) -> bool:
    """Allow mutating actions remotely only with an explicit opt-in."""
    host = (handler.headers.get("Host") or "").split(":", 1)[0].lower()
    is_local = host in {"localhost", "127.0.0.1", "::1", ""}
    return is_local or os.getenv("RELIABILITY_ALLOW_REMOTE_ACTIONS", "0").lower() in {"1", "true", "yes"}


def get_report_markdowns() -> dict[str, str]:
    inc_file = ROOT / "reports" / "incident_report.md"
    agent_file = ROOT / "reports" / "agent_log.md"
    change_file = ROOT / "docs" / "CHANGELOG.md"
    return {
        "incident_report": inc_file.read_text(encoding="utf-8") if inc_file.exists() else "",
        "agent_log": agent_file.read_text(encoding="utf-8") if agent_file.exists() else "",
        "changelog": change_file.read_text(encoding="utf-8") if change_file.exists() else "",
    }


class ReliabilityDashboardHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        # Standard HTTP access logging
        status = str(args[1]) if len(args) > 1 else "200"
        method = str(args[0]).split()[0] if len(args) > 0 else "HTTP"
        path = str(args[0]).split()[1] if len(args) > 0 and len(str(args[0]).split()) > 1 else ""
        if path.startswith("/api/status"):
            return  # Suppress high-frequency polling log noise
        color = "\033[92m" if status.startswith("2") else "\033[93m"
        log_server_event("HTTP", f"{method} {path} -> {status}", color)

    def send_json_response(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, ngrok-skip-browser-warning, Authorization")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        log_server_event("CORS", f"Preflight OPTIONS {self.path}", "\033[95m")
        self.send_response(200)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, ngrok-skip-browser-warning, Authorization")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            metrics = get_latest_metrics()
            self.send_json_response({
                "metrics": metrics,
                "action_state": LAST_ACTION_LOG,
            })
            return

        elif path == "/api/history":
            self.send_json_response(get_history_data())
            return

        elif path == "/api/lineage":
            self.send_json_response(get_lineage_data())
            return

        elif path == "/api/contracts":
            self.send_json_response(get_contract_files())
            return

        elif path == "/api/reports":
            self.send_json_response(get_report_markdowns())
            return

        # Serve static frontend files
        if path == "/" or path == "/index.html":
            file_path = STATIC_DIR / "index.html"
        else:
            rel_path = path.lstrip("/")
            file_path = STATIC_DIR / rel_path

        if file_path.exists() and file_path.is_file():
            mime_type, _ = mimetypes.guess_type(str(file_path))
            mime_type = mime_type or "application/octet-stream"
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, f"File not found: {path}")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/action":
            if not _remote_actions_allowed(self):
                log_server_event("ACTION-BLOCKED", "Remote mutating action rejected; set RELIABILITY_ALLOW_REMOTE_ACTIONS=1 to opt in.", "\033[91m")
                self.send_json_response({
                    "success": False,
                    "error": "Remote actions are disabled by default. Set RELIABILITY_ALLOW_REMOTE_ACTIONS=1 for an explicit demo opt-in.",
                }, status=403)
                return
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            action = data.get("action", "")
            log_server_event("ACTION-TRIGGER", f"Client requested action: '{action}'", "\033[96m")

            with ACTION_LOCK:
                global LAST_ACTION_LOG
                cmd: list[str] = []

                if action == "reset":
                    cmd = [str(VENV_PYTHON), str(ROOT / "scripts" / "reset_lab.py")]
                elif action == "baseline":
                    cmd = [str(VENV_PYTHON), str(ROOT / "scripts" / "run_baseline.py")]
                elif action == "pytest":
                    cmd = [str(VENV_PYTHON), "-m", "pytest", "tests_public", "-v"]
                elif action == "inject_duplicate_pk":
                    cmd = [str(VENV_PYTHON), str(ROOT / "scripts" / "inject_fault.py"), "duplicate_pk"]
                elif action == "inject_volume_drop":
                    cmd = [str(VENV_PYTHON), str(ROOT / "scripts" / "inject_fault.py"), "volume_drop"]
                elif action == "inject_stale_kb":
                    cmd = [str(VENV_PYTHON), str(ROOT / "scripts" / "inject_fault.py"), "stale_kb"]
                elif action == "gx_validate":
                    cmd = [str(VENV_PYTHON), str(ROOT / "gx" / "validate_orders.py")]
                elif action == "dbt_build":
                    dbt = ROOT / ".venv" / "Scripts" / "dbt.exe"
                    cmd = [str(dbt if dbt.exists() else "dbt"), "build", "--project-dir", str(ROOT / "dbt_project"), "--profiles-dir", str(ROOT / "dbt_project")]
                else:
                    log_server_event("ACTION-ERROR", f"Unknown action: '{action}'", "\033[91m")
                    self.send_json_response({"success": False, "error": f"Unknown action: {action}"}, status=400)
                    return

                code, output = run_subcommand(cmd)
                baseline_code = 0

                # If we injected a fault or reset, auto-run baseline
                if action in {"reset", "inject_duplicate_pk", "inject_volume_drop", "inject_stale_kb"}:
                    log_server_event("AUTO-BASELINE", "Running auto baseline calculation...", "\033[93m")
                    baseline_code, auto_baseline_out = run_subcommand([str(VENV_PYTHON), str(ROOT / "scripts" / "run_baseline.py")])
                    output += "\n--- Auto Baseline Run ---\n" + auto_baseline_out

                overall_code = code if code != 0 else baseline_code

                LAST_ACTION_LOG = {
                    "action": action,
                    "status": "success" if overall_code == 0 else "failed",
                    "output": output,
                    "command_exit_code": code,
                    "baseline_exit_code": baseline_code,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                log_server_event("ACTION-COMPLETE", f"Action '{action}' finished with status: {LAST_ACTION_LOG['status']}", "\033[92m" if overall_code == 0 else "\033[91m")

                self.send_json_response({
                    "success": overall_code == 0,
                    "action": action,
                    "output": output,
                    "metrics": get_latest_metrics(),
                })
            return

        self.send_error(404, "Endpoint not found")


def run_server(port: int = 8000) -> None:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    server_address = ("", port)
    httpd = HTTPServer(server_address, ReliabilityDashboardHandler)
    print(f"==================================================", flush=True)
    print(f"  Data Reliability Command Center Web Server", flush=True)
    print(f"  Server running at: http://localhost:{port}", flush=True)
    print(f"  Full Live Tracing: ENABLED (stdout/stderr + requests)", flush=True)
    print(f"  Remote mutating actions: {'ENABLED' if os.getenv('RELIABILITY_ALLOW_REMOTE_ACTIONS', '0').lower() in {'1', 'true', 'yes'} else 'DISABLED (set RELIABILITY_ALLOW_REMOTE_ACTIONS=1 for demo)'}", flush=True)
    print(f"  Press Ctrl+C to stop.", flush=True)
    print(f"==================================================", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...", flush=True)
        httpd.server_close()


if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)
