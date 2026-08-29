from pathlib import Path
import sys

from dashboard.server import get_contract_files, run_subcommand


ROOT = Path(__file__).resolve().parents[1]


def test_contract_api_exposes_yaml_driven_rules_and_freshness_limits():
    payload = get_contract_files()

    assert payload["orders_freshness_max_delay_minutes"] == 30
    assert payload["kb_freshness_max_delay_minutes"] == 60
    orders_currency = next(row for row in payload["orders_rules"] if row["field"] == "currency")
    assert orders_currency["severity"] == "critical"
    assert "USD" in orders_currency["constraints"]


def test_dashboard_exposes_dbt_action_and_validation_results():
    html = (ROOT / "dashboard" / "static" / "index.html").read_text(encoding="utf-8")
    server = (ROOT / "dashboard" / "server.py").read_text(encoding="utf-8")

    assert "dbt_build" in html
    assert "dbt_build" in server
    assert "contractResultsTable" in html


def test_dashboard_slo_uses_backend_warning_severity():
    app_js = (ROOT / "dashboard" / "static" / "app.js").read_text(encoding="utf-8")
    assert "PAGE / CREATE TICKET (WARNING)" in app_js
    assert "PAGE / CREATE TICKET (HIGH)" not in app_js


def test_remote_mutating_actions_are_opt_in():
    server = (ROOT / "dashboard" / "server.py").read_text(encoding="utf-8")
    assert "RELIABILITY_ALLOW_REMOTE_ACTIONS" in server
    assert 'self.send_header("Access-Control-Allow-Origin", "*")' not in server


def test_backend_action_output_contains_command_trace_markers():
    code, output = run_subcommand([sys.executable, "-c", "print('trace-line')"])
    assert code == 0
    assert "$ " in output
    assert "trace-line" in output
    assert "command_exit_code=0" in output
