// ==================== Poultry Farm Dashboard - Frontend Logic ====================
const API_BASE = window.location.origin.replace(':3000',':5000') + '/api';
const BASE_URL = 'http://localhost:5000/api';

let tempChart, humChart, historyChart;
const tempHistory = []; const humHistory = []; const timeline = [];
const MAX_POINTS = 60;

document.addEventListener('DOMContentLoaded', () => {
  initCharts();
  fetchAllData();
  setInterval(fetchAllData, 5000);  
});

function initCharts() {
  const chartOpts = (label, color) => ({
    type: 'line',
    data: { labels: [], datasets: [{ label, data: [], borderColor: color, borderWidth: 2, tension: .3, pointRadius: 0, fill: false }] },
    options: { responsive: true, maintainAspectRatio: false, scales: { x: { display: false }, y: { beginAtZero: false } }, plugins: { legend: { display: false } } }
  });

  tempChart = new Chart(document.getElementById('temp-chart'), chartOpts('Temp °C', '#e94560'));
  humChart = new Chart(document.getElementById('hum-chart'), chartOpts('Humidity %', '#42a5f5'));

  historyChart = new Chart(document.getElementById('history-chart'), {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        { label: 'Temperature °C', data: [], borderColor: '#e94560', borderWidth: 2 },
        { label: 'Humidity %', data: [], borderColor: '#42a5f5', borderWidth: 2, yAxisID: 'y1' }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { title: { display: true, text: '°C' } },
        y1: { position: 'right', title: { display: true, text: '%' }, grid: { drawOnChartArea: false } }
      }
    }
  });
}

async function fetchAllData() {
  try {
    const [liveRes, alertsRes, savingsRes] = await Promise.all([
      fetch(`${BASE_URL}/live`).catch(() => null),
      fetch(`${BASE_URL}/alerts`).catch(() => null),
      fetch(`${BASE_URL}/savings`).catch(() => null)
    ]);

    if (liveRes && liveRes.ok) {
      const liveData = await liveRes.json();
      if (liveData.success && liveData.data) updateLivePanel(liveData.data);
      document.getElementById('connection-status').textContent = '● Online';
      document.getElementById('connection-status').className = 'badge online';
    } else {
      document.getElementById('connection-status').textContent = '● Offline';
      document.getElementById('connection-status').className = 'badge offline';
    }

    if (alertsRes && alertsRes.ok) {
      const alertsData = await alertsRes.json();
      if (alertsData.success) updateAlerts(alertsData.alerts);
    }

    if (savingsRes && savingsRes.ok) {
      const savingsData = await savingsRes.json();
      if (savingsData.success) updateSavings(savingsData.savings, savingsData.monthly_projection);
    }
  } catch (e) {
    console.error('Fetch error:', e);
  }
}
function updateLivePanel(data) {

  const temp = parseFloat(data.temperature).toFixed(1);
  document.getElementById('temp-value').textContent = `${temp}°C`;
  document.getElementById('temp-target').textContent = `Target: ${data.target_temp || '--'}°C`;

  document.getElementById('hum-value').textContent = `${parseFloat(data.humidity).toFixed(0)}%`;

  const nh3 = parseFloat(data.ammonia_ppm).toFixed(1);
  document.getElementById('nh3-value').textContent = `${nh3} ppm`;
  const nh3Bar = document.getElementById('nh3-bar');
  nh3Bar.style.width = Math.min(nh3 * 2, 100) + '%';  // 50ppm = 100%
  if (nh3 < 15) nh3Bar.className = 'fill safe';
  else if (nh3 < 30) nh3Bar.className = 'fill warn';
  else nh3Bar.className = 'fill danger';

  document.getElementById('comfort-value').textContent = data.comfort_score || '--';

  document.getElementById('fan-speed').textContent = `${data.fan_speed || 0}%`;
  document.getElementById('heater-state').textContent = data.heater_state ? '🔥 ON' : '❄️ OFF';

  const distressDiv = document.getElementById('distress-value');
  const distressConf = document.getElementById('distress-confidence');
  if (data.distress_detected) {
    distressDiv.textContent = '⚠️ DISTRESS DETECTED';
    document.getElementById('distress-card').style.borderColor = '#ff1744';
    distressConf.textContent = `Confidence: ${Math.round((data.distress_confidence || 0) * 100)}%`;
  } else {
    distressDiv.textContent = '✅ Normal';
    document.getElementById('distress-card').style.borderColor = '#ffd600';
    distressConf.textContent = '';
  }
  document.getElementById('flock-day-badge').textContent = `Flock Day: ${data.flock_day || '--'}`;
  const ts = data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : '--';
  document.getElementById('last-update').textContent = `Last update: ${ts}`;
  updateChart(tempChart, temp, timeline, tempHistory, data.timestamp);
  updateChart(humChart, parseFloat(data.humidity).toFixed(0), timeline, humHistory, data.timestamp);
  updateHistoryChart(temp, parseFloat(data.humidity).toFixed(0), data.timestamp);
}

function updateChart(chart, value, labels, dataset, timestamp) {
  const timeLabel = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
  dataset.push(value);
  if (dataset.length > MAX_POINTS) dataset.shift();
  if (labels.length < dataset.length) labels.push(timeLabel);
  else if (labels.length > dataset.length) labels.shift();
  chart.data.labels = [...labels];
  chart.data.datasets[0].data = [...dataset];
  chart.update('none');
}

function updateHistoryChart(temp, hum, timestamp) {
  const label = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
  historyChart.data.labels.push(label);
  historyChart.data.datasets[0].data.push(temp);
  historyChart.data.datasets[1].data.push(hum);
  if (historyChart.data.labels.length > 100) {
    historyChart.data.labels.shift();
    historyChart.data.datasets[0].data.shift();
    historyChart.data.datasets[1].data.shift();
  }
  historyChart.update('none');
}

function updateAlerts(alerts) {
  const list = document.getElementById('alerts-list');
  if (!alerts || alerts.length === 0) {
    list.innerHTML = '<li style="background:#1b5e20">✅ No active alerts — system running normally</li>';
    return;
  }
  list.innerHTML = alerts.map(a => {
    let cls = 'info';
    if (a.severity === 'CRITICAL') cls = 'critical';
    else if (a.severity === 'HIGH' || a.severity === 'WARNING') cls = 'warning';
    return `<li class="${cls}"><strong>[${a.type}]</strong> ${a.message}</li>`;
  }).join('');
}

function updateSavings(savings, monthly) {
  document.getElementById('savings-kwh').textContent = savings.kwh_saved?.toFixed(1) || '--';
  document.getElementById('savings-cost').textContent = `$${savings.cost_saved?.toFixed(2) || '--'}`;
  document.getElementById('savings-pct').textContent = `${savings.efficiency_pct || '--'}%`;
  document.getElementById('savings-co2').textContent = savings.co2_avoided_kg?.toFixed(2) || '--';

  if (monthly && monthly.monthly_cost_saved > 0) {
    const pctEl = document.getElementById('savings-pct');
    pctEl.parentElement.querySelector('small').textContent = `Monthly: $${monthly.monthly_cost_saved.toFixed(2)}`;
  }
}
