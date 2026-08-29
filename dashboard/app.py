"""Data Reliability Command Center — Native Streamlit Interface.

Clean professional typography without emojis and clear SRE metric labels.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd
import streamlit as st

from src.contract_validator import load_contract

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "latest_metrics.json"
HISTORY = ROOT / "data" / "history" / "metrics_history.csv"
LINEAGE = ROOT / "data" / "baseline" / "lineage_graph.json"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

st.set_page_config(
    page_title="Data Reliability Command Center",
    layout="wide",
)

st.title("Data Reliability Command Center")
st.caption("Operations Dashboard, Data Contracts, Anomaly Signals, Interactive Lineage & Multi-Window SLO")

# Quick Action Bar
st.subheader("Live Operations")
ac1, ac2, ac3, ac4, ac5, ac6, ac7, ac8 = st.columns(8)

with ac1:
    if st.button("Reset Lab", use_container_width=True):
        subprocess.run([str(VENV_PYTHON), str(ROOT / "scripts" / "reset_lab.py")], cwd=str(ROOT))
        subprocess.run([str(VENV_PYTHON), str(ROOT / "scripts" / "run_baseline.py")], cwd=str(ROOT))
        st.rerun()

with ac2:
    if st.button("Run Baseline", use_container_width=True):
        subprocess.run([str(VENV_PYTHON), str(ROOT / "scripts" / "run_baseline.py")], cwd=str(ROOT))
        st.rerun()

with ac3:
    if st.button("Run Tests (all)", use_container_width=True):
        res = subprocess.run([str(VENV_PYTHON), "-m", "pytest", "tests_public", "-v"], cwd=str(ROOT), capture_output=True, text=True)
        if res.returncode == 0:
            st.success("All dashboard tests passed!")
        else:
            st.error("Test failures:\n" + res.stdout)

with ac4:
    if st.button("GX Checkpoint", use_container_width=True):
        res = subprocess.run([str(VENV_PYTHON), str(ROOT / "gx" / "validate_orders.py")], cwd=str(ROOT), capture_output=True, text=True)
        st.info(res.stdout)

with ac5:
    if st.button("Run dbt Build", use_container_width=True):
        dbt = ROOT / ".venv" / "Scripts" / "dbt.exe"
        cmd = [str(dbt if dbt.exists() else "dbt"), "build", "--project-dir", str(ROOT / "dbt_project"), "--profiles-dir", str(ROOT / "dbt_project")]
        res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        if res.returncode == 0:
            st.success("dbt build passed")
        else:
            st.error("dbt build failed:\n" + res.stdout + res.stderr)

with ac6:
    if st.button("Duplicate PK", use_container_width=True):
        subprocess.run([str(VENV_PYTHON), str(ROOT / "scripts" / "inject_fault.py"), "duplicate_pk"], cwd=str(ROOT))
        subprocess.run([str(VENV_PYTHON), str(ROOT / "scripts" / "run_baseline.py")], cwd=str(ROOT))
        st.rerun()

with ac7:
    if st.button("Volume Drop", use_container_width=True):
        subprocess.run([str(VENV_PYTHON), str(ROOT / "scripts" / "inject_fault.py"), "volume_drop"], cwd=str(ROOT))
        subprocess.run([str(VENV_PYTHON), str(ROOT / "scripts" / "run_baseline.py")], cwd=str(ROOT))
        st.rerun()

with ac8:
    if st.button("Stale KB", use_container_width=True):
        subprocess.run([str(VENV_PYTHON), str(ROOT / "scripts" / "inject_fault.py"), "stale_kb"], cwd=str(ROOT))
        subprocess.run([str(VENV_PYTHON), str(ROOT / "scripts" / "run_baseline.py")], cwd=str(ROOT))
        st.rerun()

st.divider()

if not REPORT.exists():
    st.warning("Run scripts/run_baseline.py first to generate reports/latest_metrics.json")
    st.stop()

report = json.loads(REPORT.read_text(encoding="utf-8"))
history = pd.read_csv(HISTORY) if HISTORY.exists() else pd.DataFrame()
orders_freshness_limit = load_contract(ROOT / "contracts" / "orders_contract.yaml").get("freshness", {}).get("max_delay_minutes", 30)

# Top KPI Strip
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Orders Ingested", f"{report.get('orders_rows', 0):,}")
fresh_min = report.get("freshness_minutes", 0)
c2.metric("Freshness Delay", f"{fresh_min:.1f} min", delta=f"Within SLA (≤{orders_freshness_limit}m)" if fresh_min <= orders_freshness_limit else "Exceeds SLA", delta_color="normal" if fresh_min <= orders_freshness_limit else "inverse")
c3.metric("Contract Issues", report.get("failed_contract_checks", 0), delta=f"{report.get('critical_contract_failures', 0)} Critical", delta_color="inverse" if report.get("critical_contract_failures", 0) > 0 else "off")
c4.metric("KB AI Contract", report.get("kb_failed_checks", 0))

slo = report.get("contract_slo", {})
target = slo.get("target", 0.999)
burn_rate = slo.get("burn_rate", 0.0)
budget_frac = slo.get("remaining_error_budget_fraction", 1.0)
breached = slo.get("breached", False)

c5.metric("SLO Target", f"{target*100:.2f}%", f"Allowed Err: {(1-target)*100:.2f}%")
c6.metric("Error Budget", f"{budget_frac*100:.1f}%", "Breached" if breached else f"Burn: {burn_rate:.2f}x", delta_color="inverse" if breached else "normal")

st.divider()

# Interactive Native Tabs
tab_overview, tab_contracts, tab_anomaly, tab_lineage, tab_slo, tab_reports = st.tabs([
    "Overview",
    "Data Contracts",
    "Anomaly & Drift",
    "Lineage & Blast",
    "SLO & Burn Rate",
    "Reports & Logs"
])

with tab_overview:
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Error Budget & Burn Rate")
        st.progress(float(budget_frac), text=f"Remaining Budget: {budget_frac*100:.1f}%")
        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("Actual Error Rate", f"{slo.get('actual_bad_rate', 0)*100:.3f}%")
        sc2.metric("Max Allowed Error Rate", f"{slo.get('allowed_bad_rate', 0.001)*100:.3f}%", help="100% - 99.9% Target = 0.100%")
        sc3.metric("Burn Rate", f"{burn_rate:.2f}x")

        st.subheader("Statistical Anomaly Signals")
        anom = report.get("row_count_anomaly", {})
        if anom.get("is_anomaly"):
            st.error(f"[ANOMALY DETECTED] ({anom.get('method')}): Score={anom.get('score', 0):.2f}\n\nReason: `{anom.get('reason')}`")
        else:
            st.success(f"[NORMAL] Volume Ingestion ({anom.get('method')}): Score={anom.get('score', 0):.2f}")

        kb_sig = report.get("kb_text_length_signal", {})
        if kb_sig.get("is_anomaly"):
            st.error(f"[DRIFT DETECTED] KB Document Drift: Mean={kb_sig.get('current_mean', 0):.1f} tokens")
        else:
            st.success(f"[STABLE] KB Document Distribution (Mean={kb_sig.get('current_mean', 0):.1f} tokens)")

    with col_right:
        st.subheader("Blast Radius from stg_orders")
        blast = report.get("sample_blast_radius_from_stg_orders", [])
        if blast:
            st.info("stg_orders -> " + " -> ".join([f"{b}" for b in blast]))
        
        st.subheader("Ingestion Volume History")
        if not history.empty:
            chart_data = history.set_index("date")[["row_count"]]
            st.line_chart(chart_data, color="#059669")

with tab_contracts:
    st.subheader("Data Contracts Studio")
    contract_choice = st.radio("Select Contract File", ["orders_contract.yaml", "kb_contract.yaml"], horizontal=True)
    if contract_choice == "orders_contract.yaml":
        p = ROOT / "contracts" / "orders_contract.yaml"
        if p.exists():
            st.code(p.read_text(encoding="utf-8"), language="yaml")
    else:
        p = ROOT / "contracts" / "kb_contract.yaml"
        if p.exists():
            st.code(p.read_text(encoding="utf-8"), language="yaml")
    st.subheader("Latest Validation Result")
    validation_rows = report.get("contract_results", []) + report.get("kb_contract_results", [])
    if validation_rows:
        st.dataframe(pd.DataFrame(validation_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Run a baseline to populate validation results.")

with tab_anomaly:
    st.subheader("Time-Series Metric Observability")
    if not history.empty:
        metric_sel = st.selectbox("Select Metric", ["row_count", "avg_amount", "null_rate", "mean_text_length", "embedding_norm_mean"])
        st.area_chart(history.set_index("date")[[metric_sel]])

with tab_lineage:
    st.subheader("Lineage & Downstream Impact Graph")
    if LINEAGE.exists():
        lg = json.loads(LINEAGE.read_text(encoding="utf-8"))
        ds_lineage = lg.get("dataset_lineage", {})
        col_lineage = lg.get("column_lineage", {})
        
        st.write("**Dataset Lineage:**")
        for src, targets in ds_lineage.items():
            st.write(f"- `{src}` -> {', '.join([f'`{t}`' for t in targets])}")
            
        st.write("**Column-Level Lineage:**")
        for src, targets in col_lineage.items():
            st.write(f"- `{src}` -> {', '.join([f'`{t}`' for t in targets])}")

with tab_slo:
    st.subheader("Multi-Window Burn Rate Simulator")
    short_w = st.slider("Short Window (1h) Burn Rate", 0.0, 30.0, 14.4, 0.5)
    long_w = st.slider("Long Window (6h) Burn Rate", 0.0, 30.0, 14.4, 0.5)
    
    if short_w >= 14.4 and long_w >= 14.4:
        st.error(f"PAGE ON-CALL (CRITICAL): Sustained 14.4x fast burn across 1h/6h windows. Consumes 2% budget in 1 hour.")
    elif short_w >= 6.0 and long_w >= 6.0:
        st.warning(f"PAGE / TICKET (WARNING): Sustained 6.0x fast burn across windows. Consumes 5% budget in 6 hours.")
    elif short_w >= 6.0 and long_w < 6.0:
        st.success(f"TRANSIENT SPIKE SUPPRESSED (INFO): Short window is high ({short_w:.1f}x) but long window is healthy ({long_w:.1f}x). Alert suppressed.")
    else:
        st.success(f"NORMAL OPERATING: Burn rate within safe parameters.")

with tab_reports:
    st.subheader("Incident Report & Engineering Logs")
    rep_choice = st.radio("Choose Report", ["Incident Report", "Agent Decision Log", "Changelog"], horizontal=True)
    if rep_choice == "Incident Report":
        p = ROOT / "reports" / "incident_report.md"
    elif rep_choice == "Agent Decision Log":
        p = ROOT / "reports" / "agent_log.md"
    else:
        p = ROOT / "docs" / "CHANGELOG.md"
        
    if p.exists():
        st.markdown(p.read_text(encoding="utf-8"))
