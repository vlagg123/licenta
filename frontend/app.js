const API_BASE = window.location.origin;
const WS_URL   = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`;
const MAX_CHART_POINTS = 30;
const MAX_EVENTS       = 80;

let nodes          = {};
let selectedNodeId = null;
let ws             = null;
let chartMode      = 'temperature';

let gasThresholds = {
  normal_max: 300, low_max: 450, medium_max: 600,
  high_max: 750, critical_min: 751, enable_buzzer_on_gas_high: false,
};

const GAS_LEVEL_LABELS = {
  GAS_NORMAL:   'Normal',
  GAS_LOW:      'Scazut',
  GAS_MEDIUM:   'Mediu',
  GAS_HIGH:     'Ridicat',
  GAS_CRITICAL: 'Critic',
};

const chartHistory = {
  temperature: {},
  gas:         {},
  risk:        {},
  labels:      [],
};

let nodeListEl, eventsLogEl, floorCanvas, floorCtx;
let liveChart;

const NODE_COLORS = {
  NORMAL:      '#22c55e',
  WARNING:     '#f59e0b',
  ALERT:       '#ef4444',
  OFFLINE:     '#6b7280',
  MAINTENANCE: '#8b5cf6',
};
const ZONE_NAMES = { 1:'Intrare', 2:'Depozit', 3:'Parcare', 4:'Tablou electric', 0:'Camera tehnica' };

// dimensiunile logice ale canvas-ului, scalate pt hidpi in _initCanvas
const CANVAS_W = 620;
const CANVAS_H = 420;

document.addEventListener('DOMContentLoaded', () => {
  nodeListEl  = document.getElementById('node-list');
  eventsLogEl = document.getElementById('events-log');
  floorCanvas = document.getElementById('floorplan');
  floorCtx    = floorCanvas.getContext('2d');
  _initCanvas();

  initChart();
  connectWebSocket();
  updateClock();
  setInterval(updateClock, 1000);
  fetchSystemStatus();
  setInterval(fetchSystemStatus, 10000);
  fetchEvents();
  fetchGasThresholds();
});

function _initCanvas() {
  const dpr = window.devicePixelRatio || 1;
  floorCanvas.width  = CANVAS_W * dpr;
  floorCanvas.height = CANVAS_H * dpr;
  floorCanvas.style.width  = CANVAS_W + 'px';
  floorCanvas.style.height = CANVAS_H + 'px';
  floorCtx.scale(dpr, dpr);
}

function updateClock() {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString('ro-RO');
}

function connectWebSocket() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    document.getElementById('ws-indicator').className = 'dot dot-on';
  };

  ws.onclose = () => {
    document.getElementById('ws-indicator').className = 'dot dot-off';
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = (e) => console.error('WS error', e);

  ws.onmessage = (evt) => {
    try {
      handleMessage(JSON.parse(evt.data));
    } catch(e) { console.error('WS parse error', e); }
  };
}

function handleMessage(msg) {
  switch (msg.type) {
    case 'initial_state':
      document.getElementById('mode-label').textContent = msg.mode === 'SIMULATION' ? 'SIM' : 'HW';
      msg.nodes.forEach(n => { nodes[n.node_id] = n; });
      renderAllNodes();
      drawFloorplan();
      break;

    case 'sensor_update':
      nodes[msg.node_id] = { ...(nodes[msg.node_id] || {}), ...msg };
      updateNodeCard(msg.node_id);
      updateChartHistory(msg);
      if (selectedNodeId === msg.node_id) updateDetailPanel(msg.node_id);
      drawFloorplan();
      updateSystemBadge();
      break;

    case 'node_offline':
      if (nodes[msg.node_id]) {
        nodes[msg.node_id].status = 'OFFLINE';
        updateNodeCard(msg.node_id);
        if (selectedNodeId === msg.node_id) updateDetailPanel(msg.node_id);
        drawFloorplan();
        updateSystemBadge();
      }
      break;

    case 'event':
      prependEvent(msg);
      break;

    case 'command_sent':
      showToast(`Comanda ${msg.command_type} -> Nod ${msg.target_node}`, 'ok');
      break;

    case 'thresholds_updated':
      gasThresholds = msg.thresholds;
      showToast('Praguri gaz actualizate', 'ok');
      Object.values(nodes).forEach(n => updateNodeCard(n.node_id));
      break;
  }
}

function renderAllNodes() {
  nodeListEl.innerHTML = '';
  Object.values(nodes)
    .sort((a,b) => a.node_id - b.node_id)
    .forEach(n => createNodeCard(n));
}

function createNodeCard(n) {
  const div = document.createElement('div');
  div.className = `node-card status-${n.status}`;
  div.id = `nc-${n.node_id}`;
  div.onclick = () => selectNode(n.node_id);
  div.innerHTML = nodeCardHTML(n);
  nodeListEl.appendChild(div);
}

function nodeCardHTML(n) {
  const riskW     = Math.min(100, n.risk_score || 0);
  const riskColor = riskW >= 70 ? '#ef4444' : riskW >= 40 ? '#f59e0b' : '#22c55e';
  const gasColor  = n.gas_level_color || '#22c55e';
  return `
    <div class="nc-header">
      <span class="nc-name">N${n.node_id} – ${n.zone || ZONE_NAMES[n.node_id] || '?'}</span>
      <span class="nc-badge nc-badge-${n.status}">${n.status}</span>
    </div>
    <div class="nc-metrics">
      <span><strong>${n.temperature != null ? n.temperature.toFixed(1) : '–'}°C</strong>Temp</span>
      <span><strong style="color:${gasColor}">${n.gas_value ?? '–'}</strong>Gaz</span>
      <span><strong>${n.risk_score ?? '–'}</strong>Risc</span>
      <span><strong>${n.battery ?? '–'}%</strong>Bat</span>
    </div>
    <div class="risk-bar-wrap">
      <div class="risk-bar" style="width:${riskW}%;background:${riskColor}"></div>
    </div>`;
}

function updateNodeCard(nodeId) {
  const n   = nodes[nodeId];
  const div = document.getElementById(`nc-${nodeId}`);
  if (!div) { createNodeCard(n); return; }
  div.className = `node-card status-${n.status}${selectedNodeId === nodeId ? ' selected' : ''}`;
  div.innerHTML = nodeCardHTML(n);
  div.onclick   = () => selectNode(nodeId);
}

function selectNode(nodeId) {
  selectedNodeId = nodeId;
  document.querySelectorAll('.node-card').forEach(c => c.classList.remove('selected'));
  const card = document.getElementById(`nc-${nodeId}`);
  if (card) card.classList.add('selected');
  updateDetailPanel(nodeId);
  fetchNodeRoutes(nodeId);
  // redeseneaza imediat ca linia galbena sa apara instant, nu la urmatorul pachet WS
  drawFloorplan();
}

function updateDetailPanel(nodeId) {
  const n = nodes[nodeId];
  if (!n) return;

  document.getElementById('detail-node-id').textContent = `${nodeId}`;
  document.getElementById('d-zone').textContent   = n.zone || '–';
  document.getElementById('d-status').textContent = n.status || '–';
  document.getElementById('d-status').style.color = NODE_COLORS[n.status] || '#fff';
  document.getElementById('d-risk').textContent   = n.risk_score ?? '–';
  document.getElementById('d-temp').textContent   = n.temperature != null ? `${n.temperature.toFixed(1)} °C` : '–';
  document.getElementById('d-hum').textContent    = n.humidity  != null ? `${n.humidity.toFixed(1)} %` : '–';
  document.getElementById('d-pres').textContent   = n.pressure  != null ? `${n.pressure.toFixed(1)} hPa` : '–';

  const gasLevel = n.gas_level || 'GAS_NORMAL';
  const gasColor = n.gas_level_color || '#22c55e';
  document.getElementById('d-gas').innerHTML =
    `${n.gas_value ?? '–'} &nbsp;<span class="gas-badge"><span class="gas-dot" style="background:${gasColor}"></span>${GAS_LEVEL_LABELS[gasLevel] || gasLevel}</span>`;

  document.getElementById('d-rssi').textContent = n.rssi != null ? `${n.rssi} dBm` : '–';
  document.getElementById('d-lat').textContent  = n.latency_ms != null ? `${n.latency_ms} ms` : '–';

  const batt = n.battery ?? 100;
  const bBar = document.getElementById('d-batt-bar');
  bBar.style.width      = `${batt}%`;
  bBar.style.background = batt < 20 ? '#ef4444' : batt < 40 ? '#f59e0b' : '#22c55e';
  document.getElementById('d-batt').textContent = `${batt}%`;

  const route = Array.isArray(n.route) ? n.route.map(id => id === 0 ? 'GW' : `N${id}`).join(' → ') : '–';
  document.getElementById('d-route').textContent = route;
}

async function fetchNodeRoutes(nodeId) {
  try {
    const [normal, alert] = await Promise.all([
      fetch(`${API_BASE}/api/nodes/${nodeId}/routes?alert_mode=false`).then(r => r.json()),
      fetch(`${API_BASE}/api/nodes/${nodeId}/routes?alert_mode=true`).then(r => r.json()),
    ]);
    renderRoutingInfo(nodeId, normal, alert);
  } catch(e) { console.error('Route fetch error', e); }
}

function renderRoutingInfo(nodeId, normal, alert) {
  const el = document.getElementById('routing-info');
  const destNames = { 0:'Gateway', 1:'N1 Intrare', 2:'N2 Depozit', 3:'N3 Parcare', 4:'N4 Tablou' };
  let html = `<div style="color:var(--text-muted);font-size:.7rem;margin-bottom:.5rem">Rute de la N${nodeId} (normal / alerta)</div>`;

  Object.keys(normal).forEach(dest => {
    const nr = normal[dest];
    const ar = alert[dest];
    const nPath = (nr.path||[]).map(id => id===0?'GW':`N${id}`).join('→');
    const aPath = (ar.path||[]).map(id => id===0?'GW':`N${id}`).join('→');
    html += `
      <div class="route-entry">
        <div style="font-size:.72rem;color:var(--text-muted)">${destNames[dest] || 'N'+dest}</div>
        <div class="route-path">▸ Normal: ${nPath}</div>
        <div class="route-cost">cost ${nr.cost}</div>
        <div class="route-path" style="color:#f59e0b">▸ Alerta: ${aPath}</div>
        <div class="route-cost">cost ${ar.cost}</div>
      </div>`;
  });

  el.innerHTML = html;
}

async function fetchSystemStatus() {
  try {
    const s = await fetch(`${API_BASE}/api/system/status`).then(r => r.json());
    document.getElementById('stat-online').textContent = `${s.online_nodes}/${s.total_nodes}`;
    document.getElementById('stat-alert').textContent  = s.alert_nodes;
    document.getElementById('stat-warn').textContent   = s.warning_nodes;
    document.getElementById('stat-events').textContent = s.events_today;
    document.getElementById('mode-label').textContent  = s.mode === 'SIMULATION' ? 'SIM' : 'HW';
    updateSystemBadge();
  } catch(e) {}
}

function updateSystemBadge() {
  const badge    = document.getElementById('system-status-badge');
  const statuses = Object.values(nodes).map(n => n.status);
  if (statuses.includes('ALERT')) {
    badge.className = 'badge badge-alert'; badge.textContent = 'ALERTA';
  } else if (statuses.includes('WARNING')) {
    badge.className = 'badge badge-warn'; badge.textContent = 'WARNING';
  } else if (statuses.includes('MAINTENANCE')) {
    badge.className = 'badge badge-maintenance'; badge.textContent = 'MENTENANTA';
  } else {
    badge.className = 'badge badge-ok'; badge.textContent = 'NORMAL';
  }
}

async function fetchEvents() {
  try {
    const evs = await fetch(`${API_BASE}/api/events?limit=40`).then(r => r.json());
    eventsLogEl.innerHTML = '';
    evs.forEach(e => appendEventRow(e));
  } catch(e) {}
}

function prependEvent(ev) {
  eventsLogEl.insertBefore(buildEventRow(ev), eventsLogEl.firstChild);
  if (eventsLogEl.children.length > MAX_EVENTS)
    eventsLogEl.removeChild(eventsLogEl.lastChild);
}

function appendEventRow(ev) {
  eventsLogEl.appendChild(buildEventRow(ev));
}

function buildEventRow(ev) {
  const div  = document.createElement('div');
  const ts   = new Date(ev.timestamp);
  const time = ts.toLocaleTimeString('ro-RO', { hour:'2-digit', minute:'2-digit', second:'2-digit' });
  const type = (ev.event_type || ev.status || 'INFO').toUpperCase();
  const evClass = ['ALERT','WARNING','NORMAL','OFFLINE','COMMAND'].includes(type) ? type : 'NORMAL';
  div.className = `event-row ev-${evClass}`;
  div.innerHTML = `
    <span class="ev-time">${time}</span>
    <span class="ev-zone">${ev.zone || ''}</span>
    <span class="ev-desc">${ev.description || type}</span>`;
  return div;
}

const CHART_COLORS = ['#3b82f6','#22c55e','#f59e0b','#a855f7'];

function initChart() {
  const ctx = document.getElementById('liveChart').getContext('2d');
  liveChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [1,2,3,4].map((id, i) => ({
        label: `N${id}`,
        data: [],
        borderColor: CHART_COLORS[i],
        backgroundColor: CHART_COLORS[i] + '22',
        borderWidth: 2,
        pointRadius: 2,
        tension: 0.4,
        fill: false,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { labels: { color: '#e2e8f0', font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: '#64748b', maxTicksLimit: 8 }, grid: { color: '#2a3348' } },
        y: { ticks: { color: '#64748b' }, grid: { color: '#2a3348' } },
      },
    },
  });

  [1,2,3,4].forEach(id => {
    chartHistory.temperature[id] = [];
    chartHistory.gas[id]         = [];
    chartHistory.risk[id]        = [];
  });
}

function updateChartHistory(msg) {
  const nodeId = msg.node_id;
  if (!chartHistory.temperature[nodeId]) return;

  const ts = new Date().toLocaleTimeString('ro-RO', { hour:'2-digit', minute:'2-digit', second:'2-digit' });

  chartHistory.temperature[nodeId].push(msg.temperature);
  chartHistory.gas[nodeId].push(msg.gas_value);
  chartHistory.risk[nodeId].push(msg.risk_score);

  if (chartHistory.temperature[nodeId].length > MAX_CHART_POINTS) {
    chartHistory.temperature[nodeId].shift();
    chartHistory.gas[nodeId].shift();
    chartHistory.risk[nodeId].shift();
  }

  // label-ul se adauga dupa primul nod activ din sistem, nu hard-coded nodul 1
  // daca nodul 1 e offline, nodul 2 preia etc.
  const activeNodes = Object.keys(nodes).map(Number)
    .filter(id => id > 0 && nodes[id]?.status !== 'OFFLINE')
    .sort((a, b) => a - b);
  if (activeNodes.length > 0 && activeNodes[0] === nodeId) {
    chartHistory.labels.push(ts);
    if (chartHistory.labels.length > MAX_CHART_POINTS) chartHistory.labels.shift();
    liveChart.data.labels = chartHistory.labels;
  }

  refreshChart();
}

function refreshChart() {
  [1,2,3,4].forEach((id, i) => {
    liveChart.data.datasets[i].data = [...(chartHistory[chartMode][id] || [])];
  });
  liveChart.update('none');
}

function switchChart(mode) {
  chartMode = mode;
  document.querySelectorAll('.tab-btn').forEach((b,i) => {
    b.classList.toggle('active', ['temperature','gas','risk'][i] === mode);
  });
  refreshChart();
}

const FLOOR_NODES = {
  1: { x: 90,  y: 180, label: 'N1\nIntrare' },
  2: { x: 310, y: 180, label: 'N2\nDepozit' },
  3: { x: 310, y: 340, label: 'N3\nParcare' },
  4: { x: 90,  y: 340, label: 'N4\nTableau' },
  0: { x: 510, y: 260, label: 'GW\nCamera' },
};

const FLOOR_EDGES = [[1,2],[2,3],[3,4],[4,1],[2,0]];

function drawFloorplan() {
  const g = floorCtx;
  // clearRect si grid in pixeli logici (CANVAS_W/H), nu in pixeli fizici (c.width/h)
  // dupa scale(dpr,dpr) din _initCanvas, toate coordonatele sunt in spatiul logic
  g.clearRect(0, 0, CANVAS_W, CANVAS_H);

  g.strokeStyle = '#1e2535';
  g.lineWidth = 1;
  for (let x = 0; x < CANVAS_W; x += 40) {
    g.beginPath(); g.moveTo(x, 0); g.lineTo(x, CANVAS_H); g.stroke();
  }
  for (let y = 0; y < CANVAS_H; y += 40) {
    g.beginPath(); g.moveTo(0, y); g.lineTo(CANVAS_W, y); g.stroke();
  }

  g.strokeStyle = '#2a3348'; g.lineWidth = 2;
  g.strokeRect(30, 30, 560, 360);
  g.lineWidth = 1;
  g.strokeRect(30, 30, 200, 180);
  g.strokeRect(230, 30, 200, 180);
  g.strokeRect(30, 210, 200, 180);
  g.strokeRect(230, 210, 200, 180);
  g.strokeRect(430, 30, 160, 360);

  g.fillStyle = '#2a3348'; g.font = '11px Segoe UI'; g.textAlign = 'left';
  g.fillText('Intrare',         38, 50);
  g.fillText('Depozit',         238, 50);
  g.fillText('Tablou electric', 38, 230);
  g.fillText('Parcare',         238, 230);
  g.fillText('Camera',          438, 50);
  g.fillText('Tehnica',         438, 65);

  FLOOR_EDGES.forEach(([a,b]) => {
    const na = FLOOR_NODES[a], nb = FLOOR_NODES[b];
    const broken = (nodes[a]?.status || 'NORMAL') === 'OFFLINE' ||
                   (nodes[b]?.status || 'NORMAL') === 'OFFLINE';
    g.beginPath();
    g.moveTo(na.x, na.y); g.lineTo(nb.x, nb.y);
    if (broken) {
      g.setLineDash([5,5]);
      g.strokeStyle = '#374151';
    } else {
      g.setLineDash([]);
      g.strokeStyle = '#3b82f688';
    }
    g.lineWidth = 1.5;
    g.stroke();
    g.setLineDash([]);
  });

  // ruta activa a nodului selectat
  const selNode = nodes[selectedNodeId];
  if (selNode && Array.isArray(selNode.route) && selNode.route.length > 1) {
    g.strokeStyle = '#f59e0b';
    g.lineWidth = 2.5;
    for (let i = 0; i < selNode.route.length - 1; i++) {
      const a = FLOOR_NODES[selNode.route[i]];
      const b = FLOOR_NODES[selNode.route[i+1]];
      if (a && b) { g.beginPath(); g.moveTo(a.x, a.y); g.lineTo(b.x, b.y); g.stroke(); }
    }
  }

  Object.entries(FLOOR_NODES).forEach(([idStr, pos]) => {
    const id     = parseInt(idStr);
    const n      = nodes[id];
    const status = n?.status || 'NORMAL';
    const color  = NODE_COLORS[status];
    const isGW   = id === 0;
    const r      = isGW ? 20 : 18;

    if (status === 'ALERT') {
      g.beginPath();
      g.arc(pos.x, pos.y, r + 8, 0, Math.PI*2);
      g.fillStyle = '#ef444430';
      g.fill();
    }

    g.beginPath();
    g.arc(pos.x, pos.y, r, 0, Math.PI*2);
    g.fillStyle = color + '33';
    g.fill();
    g.strokeStyle = color;
    g.lineWidth = selectedNodeId === id ? 3 : 2;
    g.stroke();

    g.fillStyle = color;
    g.font = `bold ${isGW ? 13 : 12}px Segoe UI`;
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.fillText(isGW ? 'GW' : `N${id}`, pos.x, pos.y);

    if (!isGW && n?.risk_score != null) {
      g.font = '9px Segoe UI';
      g.fillStyle = '#e2e8f0';
      g.fillText(`${n.risk_score}`, pos.x, pos.y + r + 10);
    }

    if (!isGW && n?.zone) {
      g.font = '9px Segoe UI';
      g.fillStyle = '#64748b';
      g.fillText(n.zone, pos.x, pos.y + r + 22);
    }
  });
}

async function simOffline(nodeId) {
  try {
    await post(`/api/simulation/offline/${nodeId}`);
    showToast(`N${nodeId} marcat offline`, 'warn');
  } catch(e) { showToast(`Eroare offline N${nodeId}: ${e.message}`, 'alert'); }
}

async function simResetAll() {
  try {
    await post('/api/simulation/reset');
    showToast('Sistem resetat', 'ok');
  } catch(e) { showToast(`Eroare reset: ${e.message}`, 'alert'); }
}

async function sendCmd(cmdType) {
  if (!selectedNodeId) { showToast('Selecteaza un nod mai intai!', 'warn'); return; }
  try {
    await post('/api/commands', {
      command_id:   'cmd-' + Date.now(),
      target_node:  selectedNodeId,
      command_type: cmdType,
      payload:      {},
    });
    // toast-ul vine prin WS event 'command_sent', nu il mai afisam si aici
  } catch(e) {
    showToast(`Eroare comanda ${cmdType}: ${e.message}`, 'alert');
  }
}

async function post(url, body = null) {
  const r = await fetch(API_BASE + url, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body:    body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try { const d = await r.json(); msg = d.detail || d.message || msg; } catch(_) {}
    throw new Error(msg);
  }
  return r;
}

function showToast(msg, type = 'ok') {
  const container = document.getElementById('toast-container');
  const toast     = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

async function fetchGasThresholds() {
  try {
    const t = await fetch(`${API_BASE}/api/settings/gas-thresholds`).then(r => r.json());
    gasThresholds = t;
    _populateSettingsModal(t);
  } catch(e) { console.error('fetchGasThresholds error', e); }
}

function _populateSettingsModal(t) {
  document.getElementById('th-normal-max').value    = t.normal_max;
  document.getElementById('th-low-max').value       = t.low_max;
  document.getElementById('th-medium-max').value    = t.medium_max;
  document.getElementById('th-high-max').value      = t.high_max;
  document.getElementById('th-critical-min').value  = t.critical_min;
  document.getElementById('th-buzzer-high').checked = t.enable_buzzer_on_gas_high;
}

function openSettings() {
  _populateSettingsModal(gasThresholds);
  document.getElementById('settings-overlay').classList.add('open');
}

function closeSettings(evt) {
  if (!evt || evt.target === document.getElementById('settings-overlay')) {
    document.getElementById('settings-overlay').classList.remove('open');
  }
}

async function saveThresholds() {
  const normal_max   = parseInt(document.getElementById('th-normal-max').value);
  const low_max      = parseInt(document.getElementById('th-low-max').value);
  const medium_max   = parseInt(document.getElementById('th-medium-max').value);
  const high_max     = parseInt(document.getElementById('th-high-max').value);
  const critical_min = parseInt(document.getElementById('th-critical-min').value);
  const enable_buzzer_on_gas_high = document.getElementById('th-buzzer-high').checked;

  if (normal_max >= low_max || low_max >= medium_max || medium_max >= high_max || high_max >= critical_min) {
    showToast('Pragurile trebuie sa fie in ordine crescatoare: normal < low < medium < high < critical!', 'alert');
    return;
  }

  try {
    const r      = await post('/api/settings/gas-thresholds',
                    { normal_max, low_max, medium_max, high_max, critical_min, enable_buzzer_on_gas_high });
    const result = await r.json();
    gasThresholds = result;
    showToast('Praguri salvate cu succes!', 'ok');
    document.getElementById('settings-overlay').classList.remove('open');
  } catch(e) {
    showToast(`Eroare salvare praguri: ${e.message}`, 'alert');
  }
}
