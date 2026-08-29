from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "latest_metrics.json"
HISTORY = ROOT / "data" / "history" / "metrics_history.csv"

st.set_page_config(page_title="Data Reliability Command Center", layout="wide", page_icon="🛡️")
st.title("🛡️ Data Reliability Command Center")
st.caption("Real-time Data Observability, Multi-Window SLO Burn Rate & Incident Response")

if not REPORT.exists():
    st.warning("⚠️ Run `make baseline` first to generate reports/latest_metrics.json")
    st.stop()

report = json.loads(REPORT.read_text(encoding="utf-8"))

# Top KPI metrics
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📦 Orders Ingested", f"{report.get('orders_rows', 0):,}")
c2.metric("⏱️ Freshness Lag", f"{report.get('freshness_minutes', 0):.1f} min")
c3.metric("⚠️ Contract Issues", report.get("failed_contract_checks", 0))
c4.metric("🚨 Critical Failures", report.get("critical_contract_failures", 0))
kb_fails = report.get("kb_failed_checks", 0)
c5.metric("📚 KB Contract Issues", kb_fails)

st.divider()

# Left column: Observability signals & SLO; Right column: Historical Trend & Lineage
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📊 SLI / SLO & Error Budget")
    slo = report.get("contract_slo", {})
    target = slo.get("target", 0.999)
    burn_rate = slo.get("burn_rate", 0.0)
    remaining_budget = slo.get("remaining_error_budget_fraction", 1.0)
    breached = slo.get("breached", False)

    st.progress(float(remaining_budget), text=f"Remaining Error Budget: {remaining_budget*100:.1f}%")
    
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("SLO Target", f"{target*100:.2f}%")
    sc2.metric("Burn Rate", f"{burn_rate:.2f}x")
    sc3.metric("SLO Status", "🔴 BREACHED" if breached else "🟢 HEALTHY")

    st.subheader("🔍 Anomaly Detection Signals")
    anomaly = report.get("row_count_anomaly", {})
    if anomaly.get("is_anomaly"):
        st.error(f"🚨 **Volume Anomaly Detected** ({anomaly.get('method')}): Score={anomaly.get('score', 0):.2f}\n\n*Reason:* `{anomaly.get('reason')}`")
    else:
        st.success(f"✅ **Volume Metric Healthy** ({anomaly.get('method')}): Score={anomaly.get('score', 0):.2f}")

    kb_signal = report.get("kb_text_length_signal", {})
    if kb_signal.get("is_anomaly"):
        st.error(f"🚨 **KB Document Drift Detected**: Mean Length={kb_signal.get('current_mean', 0):.1f} tokens")
    else:
        st.success(f"✅ **KB Document Distribution Stable**")

with col_right:
    st.subheader("📈 Historical Ingestion Volume")
    if HISTORY.exists():
        history = pd.read_csv(HISTORY)
        st.line_chart(history.set_index("date")[["row_count"]])

    st.subheader("🕸️ Blast Radius Analysis")
    blast_radius = report.get("sample_blast_radius_from_stg_orders", [])
    if blast_radius:
        st.info(f"**Impact Traversal from `stg_orders`:**\n\n`stg_orders` ➔ " + " ➔ ".join([f"`{a}`" for a in blast_radius]))
    else:
        st.write("No downstream dependencies.")

st.divider()
st.subheader("📑 Runbook & Incident Response Quick Links")
rc1, rc2, rc3 = st.columns(3)
rc1.markdown("[📖 Incident Report](file:///d:/Workspace/Track2-Day27-2A202601256-NguyenHungManh/reports/incident_report.md)")
rc2.markdown("[🛠️ Agent Decision Log](file:///d:/Workspace/Track2-Day27-2A202601256-NguyenHungManh/reports/agent_log.md)")
rc3.markdown("[📋 Changelog](file:///d:/Workspace/Track2-Day27-2A202601256-NguyenHungManh/docs/CHANGELOG.md)")
