/**
 * Data Reliability Command Center — Frontend Controller
 * Full interactivity, live API polling, interactive lineage canvas, Chart.js graphs,
 * and live backend action execution.
 */

// ── Application State ────────────────────────────────────────────────────────
const AppState = {
  metrics: null,
  history: [],
  lineage: { dataset_lineage: {}, column_lineage: {} },
  contracts: {},
  reports: {},
  activeTab: 'overview',
  activeContractTab: 'orders',
  activeReportTab: 'incident',
  activeMetricChart: 'row_count',
  selectedLineageNode: 'stg_orders',
  theme: localStorage.getItem('reliability_theme') || 'light',
  terminalOpen: false,
};

let overviewHistoryChartInstance = null;
let detailedMetricsChartInstance = null;

const API_HEADERS = {
  'Content-Type': 'application/json',
  'ngrok-skip-browser-warning': 'true',
};

// ── DOM Initialization ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initNavTabs();
  initLineageCanvas();
  fetchInitialData();

  // Auto-refresh metrics every 8 seconds
  setInterval(fetchStatusOnly, 8000);
});

// ── Theme Management ────────────────────────────────────────────────────────
function initTheme() {
  document.body.className = AppState.theme === 'dark' ? 'theme-dark' : 'theme-light';
  const icon = document.getElementById('themeIcon');
  if (icon) icon.textContent = AppState.theme === 'dark' ? 'light_mode' : 'dark_mode';

  document.getElementById('btnThemeToggle')?.addEventListener('click', () => {
    AppState.theme = AppState.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('reliability_theme', AppState.theme);
    initTheme();
    if (overviewHistoryChartInstance) renderOverviewChart();
    if (detailedMetricsChartInstance) renderDetailedChart();
    drawLineageGraph();
  });

  document.getElementById('btnRefreshData')?.addEventListener('click', () => {
    showToast('Refreshing all metrics...', 'info');
    fetchInitialData();
  });
}

// ── Navigation Tabs ─────────────────────────────────────────────────────────
function initNavTabs() {
  const tabs = document.querySelectorAll('.nav-item');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      const targetTab = tab.getAttribute('data-tab');
      AppState.activeTab = targetTab;

      document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
      const activePanel = document.getElementById(`tab-${targetTab}`);
      if (activePanel) activePanel.classList.add('active');

      // Refresh canvas or charts if switched into view
      if (targetTab === 'lineage') {
        setTimeout(drawLineageGraph, 50);
      } else if (targetTab === 'anomaly') {
        setTimeout(renderDetailedChart, 50);
      } else if (targetTab === 'overview') {
        setTimeout(renderOverviewChart, 50);
      } else if (targetTab === 'reports') {
        setTimeout(renderReportView, 50);
      }
    });
  });
}

// ── API Fetching ────────────────────────────────────────────────────
async function fetchInitialData() {
  try {
    const [statusRes, historyRes, lineageRes, contractsRes, reportsRes] = await Promise.all([
      fetch('/api/status', { headers: API_HEADERS }).then(r => r.json()),
      fetch('/api/history', { headers: API_HEADERS }).then(r => r.json()),
      fetch('/api/lineage', { headers: API_HEADERS }).then(r => r.json()),
      fetch('/api/contracts', { headers: API_HEADERS }).then(r => r.json()),
      fetch('/api/reports', { headers: API_HEADERS }).then(r => r.json()),
    ]);

    AppState.metrics = statusRes.metrics;
    AppState.history = historyRes;
    AppState.lineage = lineageRes;
    AppState.contracts = contractsRes;
    AppState.reports = reportsRes;

    renderAllComponents();
  } catch (err) {
    console.error('Failed to load initial data:', err);
    showToast('Backend API connecting...', 'info');
  }
}

async function fetchStatusOnly() {
  try {
    const res = await fetch('/api/status', { headers: API_HEADERS }).then(r => r.json());
    AppState.metrics = res.metrics;
    updateOverviewMetrics();
    updateHeaderStatus();
    renderContractResults();
  } catch (e) {
    // Silent fail on polling
  }
}

// ── Render Components ───────────────────────────────────────────────────────
function renderAllComponents() {
  updateHeaderStatus();
  updateOverviewMetrics();
  renderOverviewChart();
  renderDetailedChart();
  renderLineageTable();
  renderColumnLineageTable();
  drawLineageGraph();
  renderContractsView();
  renderContractResults();
  renderReportView();
  recalcSimSLO();
}

function updateHeaderStatus() {
  const m = AppState.metrics;
  if (!m) return;

  const totalIssues = (m.failed_contract_checks || 0) + (m.kb_failed_checks || 0);
  const critical = m.critical_contract_failures || 0;
  const isAnomaly = m.row_count_anomaly?.is_anomaly || false;
  const breached = m.contract_slo?.breached || false;

  const isHealthy = totalIssues === 0 && !isAnomaly && !breached;
  const statusBadge = document.getElementById('headerStatusBadge');
  const liveDot = document.getElementById('systemLiveDot');

  if (statusBadge) {
    if (isHealthy) {
      statusBadge.className = 'header-status badge-green';
      statusBadge.innerHTML = '<span class="material-icons-outlined status-icon">check_circle</span><span class="status-label">HEALTHY</span>';
      if (liveDot) liveDot.style.backgroundColor = 'var(--color-green)';
    } else if (critical > 0 || breached) {
      statusBadge.className = 'header-status badge-red';
      statusBadge.innerHTML = '<span class="material-icons-outlined status-icon">cancel</span><span class="status-label">CRITICAL</span>';
      if (liveDot) liveDot.style.backgroundColor = 'var(--color-red)';
    } else {
      statusBadge.className = 'header-status badge-yellow';
      statusBadge.innerHTML = '<span class="material-icons-outlined status-icon">warning</span><span class="status-label">WARNING</span>';
      if (liveDot) liveDot.style.backgroundColor = 'var(--color-amber)';
    }
  }
}

function updateOverviewMetrics() {
  const m = AppState.metrics;
  if (!m) return;

  // 1. Orders
  document.getElementById('valOrdersRows').textContent = (m.orders_rows || 0).toLocaleString();

  // 2. Freshness
  const freshMin = m.freshness_minutes || 0;
  const freshnessLimit = Number(AppState.contracts.orders_freshness_max_delay_minutes || 30);
  const freshEl = document.getElementById('valFreshnessMin');
  const freshBadge = document.getElementById('badgeFreshness');
  freshEl.innerHTML = `${freshMin.toFixed(1)}<span style="font-size:14px;color:var(--text-subtle)"> min</span>`;
  const freshnessSummary = document.getElementById('ordersFreshnessSummary');
  if (freshnessSummary) freshnessSummary.textContent = `Max lag: ${freshnessLimit} mins (orders_contract.yaml)`;
  if (freshMin <= freshnessLimit) {
    freshBadge.className = 'badge badge-green';
    freshBadge.textContent = `Within SLA (≤ ${freshnessLimit}m)`;
  } else {
    freshBadge.className = 'badge badge-yellow';
    freshBadge.textContent = `Exceeds SLA (>${freshnessLimit}m)`;
  }

  // 3. Contract Issues
  const issues = m.failed_contract_checks || 0;
  const crit = m.critical_contract_failures || 0;
  document.getElementById('valContractIssues').textContent = issues;
  const critBadge = document.getElementById('badgeContractCritical');
  if (issues === 0) {
    critBadge.className = 'badge badge-green';
    critBadge.textContent = '0 Issues';
  } else {
    critBadge.className = crit > 0 ? 'badge badge-red' : 'badge badge-yellow';
    critBadge.textContent = `${crit} Critical (${issues} Total)`;
  }

  // 4. KB Contract
  const kbIssues = m.kb_failed_checks || 0;
  document.getElementById('valKBContractIssues').textContent = kbIssues;
  const kbBadge = document.getElementById('badgeKBIssues');
  if (kbIssues === 0) {
    kbBadge.className = 'badge badge-green';
    kbBadge.textContent = '0 Issues';
  } else {
    kbBadge.className = 'badge badge-yellow';
    kbBadge.textContent = `${kbIssues} Issue(s)`;
  }

  // 5. SLO & Budget
  const slo = m.contract_slo || {};
  const target = slo.target || 0.999;
  const burn = slo.burn_rate || 0.0;
  const budgetFrac = slo.remaining_error_budget_fraction !== undefined ? slo.remaining_error_budget_fraction : 1.0;
  const breached = slo.breached || false;

  document.getElementById('valSLOTarget').textContent = `${(target * 100).toFixed(1)}%`;
  document.getElementById('badgeSLOBurn').textContent = `Burn: ${burn.toFixed(2)}x`;

  const budgetPct = (budgetFrac * 100).toFixed(1);
  const budgetValEl = document.getElementById('valBudgetFraction');
  budgetValEl.innerHTML = `${budgetPct}<span style="font-size:14px;color:var(--text-subtle)">%</span>`;

  const budgetStatusBadge = document.getElementById('badgeBudgetStatus');
  const panelSLOBadge = document.getElementById('panelSLOBadge');
  const sloProgressBar = document.getElementById('sloProgressBar');
  const sloBudgetPercent = document.getElementById('sloBudgetPercent');

  document.getElementById('sloActualBad').textContent = `${((slo.actual_bad_rate || 0) * 100).toFixed(3)}%`;
  document.getElementById('sloAllowedBad').textContent = `${((slo.allowed_bad_rate || 0.001) * 100).toFixed(3)}%`;
  document.getElementById('sloBurnRate').textContent = `${burn.toFixed(2)}x`;

  if (sloBudgetPercent) sloBudgetPercent.textContent = `${budgetPct}%`;
  if (sloProgressBar) {
    sloProgressBar.style.width = `${budgetPct}%`;
    if (budgetFrac > 0.5) {
      sloProgressBar.className = 'progress-bar-fill fill-green';
    } else if (budgetFrac > 0.2) {
      sloProgressBar.className = 'progress-bar-fill fill-yellow';
    } else {
      sloProgressBar.className = 'progress-bar-fill fill-red';
    }
  }

  if (breached) {
    budgetStatusBadge.className = 'badge badge-red';
    budgetStatusBadge.textContent = 'Breached';
    if (panelSLOBadge) { panelSLOBadge.className = 'badge badge-red'; panelSLOBadge.textContent = 'SLO Breached'; }
  } else {
    budgetStatusBadge.className = 'badge badge-green';
    budgetStatusBadge.textContent = 'Healthy';
    if (panelSLOBadge) { panelSLOBadge.className = 'badge badge-green'; panelSLOBadge.textContent = 'Budget Healthy'; }
  }

  // 6. Anomaly Signals
  const volAnom = m.row_count_anomaly || {};
  const sigVolBadge = document.getElementById('sigVolumeBadge');
  const sigVolScore = document.getElementById('sigVolumeScore');
  const sigVolMethod = document.getElementById('sigVolumeMethod');
  if (sigVolBadge) {
    sigVolScore.textContent = `Score: ${(volAnom.score || 0).toFixed(2)}`;
    sigVolMethod.textContent = `Method: ${volAnom.method || 'N/A'}`;
    if (volAnom.is_anomaly) {
      sigVolBadge.className = 'badge badge-red';
      sigVolBadge.textContent = 'ANOMALY';
    } else {
      sigVolBadge.className = 'badge badge-green';
      sigVolBadge.textContent = 'NORMAL';
    }
  }

  const kbAnom = m.kb_text_length_signal || {};
  const sigKBBadge = document.getElementById('sigKBBadge');
  const sigKBScore = document.getElementById('sigKBScore');
  const sigKBMethod = document.getElementById('sigKBMethod');
  if (sigKBBadge) {
    sigKBScore.textContent = `Score: ${(kbAnom.score || 0).toFixed(2)}`;
    sigKBMethod.textContent = `Mean: ${(kbAnom.current_mean || 0).toFixed(1)} tokens`;
    if (kbAnom.is_anomaly) {
      sigKBBadge.className = 'badge badge-red';
      sigKBBadge.textContent = 'DRIFT';
    } else {
      sigKBBadge.className = 'badge badge-green';
      sigKBBadge.textContent = 'STABLE';
    }
  }

  // 7. Blast radius summary
  const blast = m.sample_blast_radius_from_stg_orders || [];
  const blastCountEl = document.getElementById('badgeBlastCount');
  if (blastCountEl) blastCountEl.textContent = `${blast.length} Downstream`;

  // 8. Overall Action Badge
  const actionBadge = document.getElementById('overviewActionBadge');
  if (actionBadge) {
    if (crit > 0) {
      actionBadge.className = 'badge badge-red';
      actionBadge.textContent = 'BLOCK';
    } else if (issues > 0) {
      actionBadge.className = 'badge badge-yellow';
      actionBadge.textContent = 'QUARANTINE';
    } else {
      actionBadge.className = 'badge badge-green';
      actionBadge.textContent = 'PASS';
    }
  }
}

// ── Chart.js Renderers ──────────────────────────────────────────────────────
function renderOverviewChart() {
  const ctx = document.getElementById('overviewHistoryChart');
  if (!ctx || !AppState.history.length) return;

  const isDark = AppState.theme === 'dark';
  const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)';
  const textColor = isDark ? '#a4bab7' : '#8a9e9b';

  const labels = AppState.history.map(d => d.date.substring(5));
  const data = AppState.history.map(d => d.row_count);

  if (overviewHistoryChartInstance) overviewHistoryChartInstance.destroy();

  overviewHistoryChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Orders Ingested',
        data,
        borderColor: '#059669',
        backgroundColor: isDark ? 'rgba(5, 150, 105, 0.15)' : 'rgba(5, 150, 105, 0.08)',
        fill: true,
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 2,
        pointHoverRadius: 5,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: isDark ? '#1c2b2a' : '#ffffff',
          titleColor: isDark ? '#e6f0ee' : '#1a2b2a',
          bodyColor: isDark ? '#a4bab7' : '#4a5c5a',
          borderColor: isDark ? '#273b39' : '#e2e8e6',
          borderWidth: 1,
          padding: 10,
        }
      },
      scales: {
        x: { grid: { color: gridColor }, ticks: { color: textColor, font: { size: 10 } } },
        y: { grid: { color: gridColor }, ticks: { color: textColor, font: { size: 10 } } }
      }
    }
  });
}

function switchMetricChart(metric) {
  AppState.activeMetricChart = metric;
  document.querySelectorAll('#tab-anomaly .subtab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.toLowerCase().includes(metric.replace('_', ' ')));
  });
  renderDetailedChart();
}

function renderDetailedChart() {
  const ctx = document.getElementById('detailedMetricsChart');
  if (!ctx || !AppState.history.length) return;

  const isDark = AppState.theme === 'dark';
  const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)';
  const textColor = isDark ? '#a4bab7' : '#8a9e9b';

  const metric = AppState.activeMetricChart;
  const labels = AppState.history.map(d => d.date);
  const values = AppState.history.map(d => d[metric]);

  const colorMap = {
    row_count: { border: '#059669', bg: 'rgba(5,150,105,0.1)' },
    avg_amount: { border: '#4f46e5', bg: 'rgba(79,70,229,0.1)' },
    null_rate: { border: '#d97706', bg: 'rgba(217,119,6,0.1)' },
    mean_text_length: { border: '#7c3aed', bg: 'rgba(124,58,237,0.1)' },
    embedding_norm_mean: { border: '#2563eb', bg: 'rgba(37,99,235,0.1)' },
  };

  const colors = colorMap[metric] || colorMap.row_count;

  if (detailedMetricsChartInstance) detailedMetricsChartInstance.destroy();

  detailedMetricsChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: metric.replace(/_/g, ' ').toUpperCase(),
        data: values,
        borderColor: colors.border,
        backgroundColor: colors.bg,
        fill: true,
        tension: 0.3,
        borderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: textColor } },
        tooltip: {
          backgroundColor: isDark ? '#1c2b2a' : '#ffffff',
          titleColor: isDark ? '#e6f0ee' : '#1a2b2a',
          bodyColor: isDark ? '#a4bab7' : '#4a5c5a',
          borderColor: isDark ? '#273b39' : '#e2e8e6',
          borderWidth: 1,
        }
      },
      scales: {
        x: { grid: { color: gridColor }, ticks: { color: textColor, font: { size: 10 } } },
        y: { grid: { color: gridColor }, ticks: { color: textColor, font: { size: 10 } } }
      }
    }
  });
}

// ── Lineage Canvas & Blast Radius ───────────────────────────────────────────
const LINEAGE_NODES = {
  raw_orders: { x: 80, y: 80, label: 'raw_orders', type: 'source' },
  stg_orders: { x: 300, y: 80, label: 'stg_orders', type: 'mart' },
  fct_daily_revenue: { x: 560, y: 120, label: 'fct_daily_revenue', type: 'mart' },
  ceo_revenue_dashboard: { x: 820, y: 120, label: 'ceo_revenue_dashboard', type: 'consumer' },

  raw_customers: { x: 80, y: 180, label: 'raw_customers', type: 'source' },
  stg_customers: { x: 300, y: 180, label: 'stg_customers', type: 'mart' },

  kb_documents: { x: 80, y: 280, label: 'kb_documents', type: 'source' },
  kb_active_docs: { x: 300, y: 280, label: 'kb_active_docs', type: 'mart' },
  rag_index: { x: 560, y: 280, label: 'rag_index', type: 'mart' },
  support_agent: { x: 820, y: 280, label: 'support_agent', type: 'consumer' },
};

function initLineageCanvas() {
  const canvas = document.getElementById('lineageCanvas');
  if (!canvas) return;

  canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const clickX = (e.clientX - rect.left) * scaleX;
    const clickY = (e.clientY - rect.top) * scaleY;

    for (const [id, node] of Object.entries(LINEAGE_NODES)) {
      const dist = Math.hypot(clickX - node.x, clickY - node.y);
      if (dist < 36) {
        AppState.selectedLineageNode = id;
        drawLineageGraph();
        updateBlastInfo(id);
        break;
      }
    }
  });
}

function getTransitiveDownstream(startNode) {
  const graph = AppState.lineage.dataset_lineage || {};
  const seen = new Set([startNode]);
  const queue = [startNode];
  const out = [];

  while (queue.length > 0) {
    const curr = queue.shift();
    const children = graph[curr] || [];
    for (const child of children) {
      if (!seen.has(child)) {
        seen.add(child);
        out.push(child);
        queue.push(child);
      }
    }
  }
  return out;
}

function drawLineageGraph() {
  const canvas = document.getElementById('lineageCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const isDark = AppState.theme === 'dark';

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const selected = AppState.selectedLineageNode;
  const affected = new Set(getTransitiveDownstream(selected));

  const graph = AppState.lineage.dataset_lineage || {};

  // 1. Draw Edges
  for (const [parent, children] of Object.entries(graph)) {
    const pNode = LINEAGE_NODES[parent];
    if (!pNode) continue;

    for (const child of children) {
      const cNode = LINEAGE_NODES[child];
      if (!cNode) continue;

      const isAffectedEdge = (parent === selected || affected.has(parent)) && affected.has(child);

      ctx.beginPath();
      ctx.moveTo(pNode.x + 40, pNode.y);
      ctx.lineTo(cNode.x - 40, cNode.y);
      ctx.strokeStyle = isAffectedEdge ? '#ef4444' : (isDark ? '#273b39' : '#cbd5e1');
      ctx.lineWidth = isAffectedEdge ? 3 : 1.5;
      if (isAffectedEdge) ctx.setLineDash([4, 2]);
      else ctx.setLineDash([]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Arrow head
      const angle = Math.atan2(cNode.y - pNode.y, cNode.x - 40 - (pNode.x + 40));
      ctx.fillStyle = isAffectedEdge ? '#ef4444' : (isDark ? '#273b39' : '#cbd5e1');
      ctx.beginPath();
      ctx.arc(cNode.x - 42, cNode.y, 4, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // 2. Draw Nodes
  for (const [id, node] of Object.entries(LINEAGE_NODES)) {
    const isSelected = id === selected;
    const isImpacted = affected.has(id);

    ctx.beginPath();
    ctx.roundRect(node.x - 55, node.y - 18, 110, 36, 8);

    if (isSelected) {
      ctx.fillStyle = isDark ? '#7f1d1d' : '#fef2f2';
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 2.5;
    } else if (isImpacted) {
      ctx.fillStyle = isDark ? '#78350f' : '#fffbeb';
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 2;
    } else {
      ctx.fillStyle = isDark ? '#15201f' : '#ffffff';
      ctx.strokeStyle = isDark ? '#273b39' : '#e2e8e6';
      ctx.lineWidth = 1;
    }

    ctx.fill();
    ctx.stroke();

    // Node Label
    ctx.font = '600 11px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = isSelected ? '#ef4444' : (isImpacted ? '#d97706' : (isDark ? '#e6f0ee' : '#1a2b2a'));
    ctx.fillText(node.label, node.x, node.y);
  }
}

function updateBlastInfo(nodeId) {
  const downstream = getTransitiveDownstream(nodeId);
  const infoEl = document.getElementById('interactiveBlastInfo');
  if (!infoEl) return;

  if (downstream.length === 0) {
    infoEl.innerHTML = `<span class="material-icons-outlined text-green">check_circle</span><span>Node <strong>${nodeId}</strong> is a terminal asset (no downstream dependencies).</span>`;
  } else {
    const list = downstream.map(d => `<code>${d}</code>`).join(' &rarr; ');
    infoEl.innerHTML = `<span class="material-icons-outlined text-amber">warning</span><span>Blast radius from <strong>${nodeId}</strong> impacts ${downstream.length} asset(s): ${list}</span>`;
  }
}

function renderLineageTable() {
  const tbody = document.getElementById('overviewLineageTbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const graph = AppState.lineage.dataset_lineage || {};
  for (const [src, targets] of Object.entries(graph)) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td><strong>${src}</strong></td><td>${targets.map(t => `<span class="badge badge-subtle">${t}</span>`).join(' ')}</td>`;
    tbody.appendChild(tr);
  }
}

function renderColumnLineageTable() {
  const tbody = document.getElementById('columnLineageTbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const colGraph = AppState.lineage.column_lineage || {};
  for (const [srcCol, targetCols] of Object.entries(colGraph)) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td><code>${srcCol}</code></td><td>${targetCols.map(t => `<code>${t}</code>`).join(' &rarr; ')}</td>`;
    tbody.appendChild(tr);
  }
}

// ── Contracts Studio ────────────────────────────────────────────────────────
function switchContractTab(tab) {
  AppState.activeContractTab = tab;
  document.querySelectorAll('#tab-contracts .subtab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.includes(tab));
  });
  renderContractsView();
}

function renderContractsView() {
  const yamlViewer = document.getElementById('contractYamlViewer');
  const tbody = document.getElementById('contractRulesTbody');
  if (!yamlViewer || !tbody) return;

  const raw = AppState.activeContractTab === 'orders' 
    ? AppState.contracts.orders_contract 
    : AppState.contracts.kb_contract;

  yamlViewer.textContent = raw || 'Contract file not found.';
  tbody.innerHTML = '';

  const rules = AppState.activeContractTab === 'orders'
    ? (AppState.contracts.orders_rules || [])
    : (AppState.contracts.kb_rules || []);
  rules.forEach(r => {
    const tr = document.createElement('tr');
    const field = document.createElement('td');
    field.innerHTML = `<strong>${r.field}</strong>`;
    const type = document.createElement('td');
    type.innerHTML = `<code>${r.type}</code>`;
    const constraints = document.createElement('td');
    constraints.textContent = r.constraints || '—';
    const severity = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = `badge ${r.severity === 'critical' ? 'badge-red' : 'badge-yellow'}`;
    badge.textContent = String(r.severity || 'warning').toUpperCase();
    severity.appendChild(badge);
    [field, type, constraints, severity].forEach(cell => tr.appendChild(cell));
    tbody.appendChild(tr);
  });
}

function renderContractResults() {
  const table = document.getElementById('contractResultsTable');
  const tbody = document.getElementById('contractResultsTbody');
  if (!table || !tbody) return;
  const m = AppState.metrics || {};
  const results = [...(m.contract_results || []), ...(m.kb_contract_results || [])];
  tbody.innerHTML = '';
  const setOverviewStatus = (id, passed, label = null) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = `badge ${passed ? 'badge-green' : 'badge-red'}`;
    el.textContent = label || (passed ? 'PASS' : 'FAIL');
  };
  setOverviewStatus('rowStatusSchema', (m.failed_contract_checks || 0) === 0);
  setOverviewStatus('rowStatusFreshness', Number(m.freshness_minutes || 0) <= Number(AppState.contracts.orders_freshness_max_delay_minutes || 30));
  setOverviewStatus('rowStatusKB', (m.kb_failed_checks || 0) === 0);
  if (!results.length) {
    const row = document.createElement('tr');
    row.innerHTML = '<td colspan="5" class="table-subtext">No baseline validation has been recorded yet.</td>';
    tbody.appendChild(row);
    return;
  }
  results.forEach(result => {
    const row = document.createElement('tr');
    const status = result.passed ? 'PASS' : 'FAIL';
    const statusClass = result.passed ? 'badge-green' : (result.severity === 'critical' ? 'badge-red' : 'badge-yellow');
    row.innerHTML = `<td>${result.check || '—'}</td><td>${result.column || '—'}</td><td><span class="badge ${statusClass}">${status}</span></td><td>${String(result.severity || 'warning').toUpperCase()}</td><td>${result.details || ''}</td>`;
    tbody.appendChild(row);
  });
}

// ── SLO Multi-Window Simulator ──────────────────────────────────────────────
function setSLOPreset(short, long) {
  document.getElementById('simShortInput').value = short;
  document.getElementById('simLongInput').value = long;
  recalcSimSLO();
}

function recalcSimSLO() {
  const target = parseFloat(document.getElementById('simTargetInput')?.value || 99.9);
  const short = parseFloat(document.getElementById('simShortInput')?.value || 14.4);
  const long = parseFloat(document.getElementById('simLongInput')?.value || 14.4);

  document.getElementById('simTargetVal').textContent = `${target.toFixed(2)}%`;
  document.getElementById('simShortVal').textContent = `${short.toFixed(1)}x`;
  document.getElementById('simLongVal').textContent = `${long.toFixed(1)}x`;

  const card = document.getElementById('simDecisionCard');
  const iconBox = document.getElementById('simDecisionIconBox');
  const icon = document.getElementById('simDecisionIcon');
  const title = document.getElementById('simDecisionTitle');
  const reason = document.getElementById('simDecisionReason');

  if (!card) return;

  if (short >= 14.4 && long >= 14.4) {
    card.style.backgroundColor = 'var(--color-red-light)';
    card.style.borderColor = 'var(--color-red-border)';
    iconBox.style.backgroundColor = 'var(--color-red)';
    icon.textContent = 'notifications_active';
    title.textContent = 'PAGE ON-CALL (CRITICAL)';
    title.style.color = 'var(--color-red)';
    reason.textContent = `Sustained 14.4x fast burn rate detected across both 1h and 6h windows (Short=${short.toFixed(1)}x, Long=${long.toFixed(1)}x). 2% of budget burned in 1 hour.`;
  } else if (short >= 6.0 && long >= 6.0) {
    card.style.backgroundColor = 'var(--color-amber-light)';
    card.style.borderColor = 'var(--color-amber-border)';
    iconBox.style.backgroundColor = 'var(--color-amber)';
    icon.textContent = 'warning';
    title.textContent = 'PAGE / CREATE TICKET (WARNING)';
    title.style.color = 'var(--color-amber)';
    reason.textContent = `Sustained 6.0x fast burn rate across windows (Short=${short.toFixed(1)}x, Long=${long.toFixed(1)}x). Consuming 5% of error budget in 6 hours.`;
  } else if (short >= 6.0 && long < 6.0) {
    card.style.backgroundColor = 'var(--color-green-light)';
    card.style.borderColor = 'var(--color-green-border)';
    iconBox.style.backgroundColor = 'var(--color-green)';
    icon.textContent = 'filter_alt';
    title.textContent = 'TRANSIENT SPIKE SUPPRESSED (INFO)';
    title.style.color = 'var(--color-green)';
    reason.textContent = `Short window burn rate is high (${short.toFixed(1)}x), but long window remains healthy (${long.toFixed(1)}x). Alert suppressed to prevent on-call fatigue.`;
  } else {
    card.style.backgroundColor = 'var(--color-green-light)';
    card.style.borderColor = 'var(--color-green-border)';
    iconBox.style.backgroundColor = 'var(--color-green)';
    icon.textContent = 'check_circle';
    title.textContent = 'NORMAL OPERATING CONDITIONS';
    title.style.color = 'var(--color-green)';
    reason.textContent = `Burn rate is within safe operating parameters (Short=${short.toFixed(1)}x, Long=${long.toFixed(1)}x). Error budget is protected.`;
  }
}

// ── Reports Viewer (Render Markdown via Marked.js) ──────────────────────────
function switchReportTab(tab) {
  AppState.activeReportTab = tab;
  document.querySelectorAll('#tab-reports .subtab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.toLowerCase().includes(tab));
  });
  renderReportView();
}

function renderReportView() {
  const box = document.getElementById('reportViewerBox');
  if (!box) return;

  let rawMd = '';
  if (AppState.activeReportTab === 'incident') {
    rawMd = AppState.reports.incident_report || '# Incident Report\nNo incident report available.';
  } else if (AppState.activeReportTab === 'agent') {
    rawMd = AppState.reports.agent_log || '# Agent Decision Log\nNo decision log available.';
  } else {
    rawMd = AppState.reports.changelog || '# Changelog\nNo changelog available.';
  }

  if (window.marked) {
    box.innerHTML = marked.parse(rawMd);
  } else {
    box.textContent = rawMd;
  }
}

// ── Live Backend Actions ────────────────────────────────────────────────────
async function executeBackendAction(actionName) {
  showToast(`Executing action: ${actionName}...`, 'info');
  openTerminal();
  appendTerminalLog(`\n>>> EXECUTING ACTION: ${actionName} @ ${new Date().toLocaleTimeString()}...\n`);

  try {
    const res = await fetch('/api/action', {
      method: 'POST',
      headers: API_HEADERS,
      body: JSON.stringify({ action: actionName }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.error || `Server returned status HTTP ${res.status}`;
      appendTerminalLog(`ERROR: ${detail}`);
      throw new Error(detail);
    }
    appendTerminalLog(data.output || 'No output returned.');

    if (data.success) {
      showToast(`Action ${actionName} completed successfully!`, 'success');
      AppState.metrics = data.metrics;
      updateOverviewMetrics();
      updateHeaderStatus();
      renderContractResults();
    } else {
      showToast(`Action ${actionName} completed with alert/failure.`, 'warning');
      if (data.metrics) {
        AppState.metrics = data.metrics;
        updateOverviewMetrics();
        updateHeaderStatus();
        renderContractResults();
      }
    }
  } catch (err) {
    appendTerminalLog(`ERROR: Failed to communicate with backend: ${err.message}`);
    showToast(`Execution error: ${err.message}`, 'error');
  }
}

// ── Terminal Drawer Controller ──────────────────────────────────────────────
function toggleTerminalLog() {
  AppState.terminalOpen = !AppState.terminalOpen;
  const drawer = document.getElementById('terminalDrawer');
  if (drawer) drawer.classList.toggle('open', AppState.terminalOpen);
}

function openTerminal() {
  AppState.terminalOpen = true;
  const drawer = document.getElementById('terminalDrawer');
  if (drawer) drawer.classList.add('open');
}

function clearTerminal() {
  const body = document.getElementById('terminalOutput');
  if (body) body.textContent = 'Terminal cleared. Ready.';
}

function appendTerminalLog(text) {
  const body = document.getElementById('terminalOutput');
  if (body) {
    body.textContent += '\n' + text;
    body.scrollTop = body.scrollHeight;
  }
}

// ── Toast Notifications ─────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast badge-${type === 'success' ? 'green' : (type === 'error' ? 'red' : (type === 'warning' ? 'yellow' : 'subtle'))}`;
  
  const icon = type === 'success' ? 'check_circle' : (type === 'error' ? 'cancel' : (type === 'warning' ? 'warning' : 'info'));
  toast.innerHTML = `<span class="material-icons-outlined">${icon}</span><span>${message}</span>`;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}
