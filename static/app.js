const GROUPS = {
  comfort: {
    title: "Comfort",
    fields: ["temp", "humid", "dew_point", "abs_humid"],
  },
  co2: {
    title: "CO2",
    fields: ["co2", "co2_est"],
  },
  voc: {
    title: "VOC",
    fields: ["voc", "voc_h2_raw", "voc_ethanol_raw"],
  },
  particulates: {
    title: "Particulates",
    fields: ["pm25", "pm10_est"],
  },
  score: {
    title: "Score",
    fields: ["score"],
  },
  radiation: {
    title: "Radiation",
    fields: ["cpm"],
  },
};

const LABELS = {
  score: "Score",
  dew_point: "Dew point",
  temp: "Temperature",
  humid: "Humidity",
  abs_humid: "Abs. humidity",
  co2: "CO2",
  co2_est: "CO2 estimate",
  voc: "VOC",
  voc_h2_raw: "VOC H2 raw",
  voc_ethanol_raw: "VOC ethanol raw",
  pm25: "PM2.5",
  pm10_est: "PM10 estimate",
  cpm: "CPM",
};

const UNITS = {
  temp: " C",
  dew_point: " C",
  humid: "%",
  abs_humid: " g/m3",
  co2: " ppm",
  co2_est: " ppm",
  pm25: " ug/m3",
  pm10_est: " ug/m3",
  cpm: " cpm",
};

const COLORS = {
  score: "#16735f",
  dew_point: "#516a9f",
  temp: "#c5533d",
  humid: "#2381a5",
  abs_humid: "#8b6bb8",
  co2: "#b14f9b",
  co2_est: "#7d6a1f",
  voc: "#b65f19",
  voc_h2_raw: "#237a77",
  voc_ethanol_raw: "#8f4d64",
  pm25: "#3a78bf",
  pm10_est: "#72913a",
  cpm: "#d32f2f",
};

const state = {
  group: "comfort",
  readings: [],
  enabled: new Set(Object.values(GROUPS).flatMap((group) => group.fields)),
  mouseX: null,
  latestAir: null,
  latestRad: null,
};

const chart = document.getElementById("chart");
const ctx = chart.getContext("2d");
const statusEl = document.getElementById("status");
const latestEl = document.getElementById("latest");
const groupsEl = document.getElementById("groups");
const togglesEl = document.getElementById("toggles");
const hoursEl = document.getElementById("hours");
const titleEl = document.getElementById("chart-title");
const pointCountEl = document.getElementById("point-count");
const metricGridEl = document.getElementById("metric-grid");
const diagBadgeEl = document.getElementById("diag-badge");
const diagStatsEl = document.getElementById("diag-stats");
const diagRowsEl = document.getElementById("diag-rows");

function init() {
  renderGroupButtons();
  renderToggles();
  hoursEl.addEventListener("change", loadReadings);
  window.addEventListener("resize", drawChart);
  chart.addEventListener("mousemove", (e) => {
    const rect = chart.getBoundingClientRect();
    state.mouseX = e.clientX - rect.left;
    drawChart();
  });
  chart.addEventListener("mouseleave", () => {
    state.mouseX = null;
    drawChart();
  });
  acInit();
  loadReadings();
  loadDiagnostics();
  loadAc();
  setInterval(loadReadings, 10000);
  setInterval(loadDiagnostics, 30000);
  setInterval(loadAc, 15000);
}

async function loadDiagnostics() {
  let payload;
  try {
    const res = await fetch("/api/errors?limit=20");
    if (!res.ok) return;
    payload = await res.json();
  } catch (err) {
    console.error("Diagnostics load failed:", err);
    return;
  }
  renderDiagnostics(payload.stats || {}, payload.errors || []);
}

function renderDiagnostics(stats, errors) {
  const total = stats.total || 0;
  const last24 = stats.last_24h || 0;

  diagBadgeEl.textContent = total === 0 ? "No errors" : `${last24} in 24h / ${total} total`;
  diagBadgeEl.classList.toggle("ok", total === 0);
  diagBadgeEl.classList.toggle("warn", total > 0);

  diagStatsEl.replaceChildren();
  const stat = (label, value) => {
    const el = document.createElement("div");
    el.className = "diag-stat";
    el.innerHTML = `<span class="label">${label}</span><span class="value">${value}</span>`;
    return el;
  };
  diagStatsEl.append(
    stat("Total", total),
    stat("Last 24h", last24),
    stat("Last error", stats.last_at ? new Date(stats.last_at).toLocaleString() : "-")
  );
  (stats.by_stage || []).forEach((s) => diagStatsEl.append(stat(s.stage, s.count)));

  diagRowsEl.replaceChildren();
  if (!errors.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="3" class="diag-empty">No errors recorded</td>`;
    diagRowsEl.append(tr);
    return;
  }
  errors.forEach((e) => {
    const tr = document.createElement("tr");
    const time = document.createElement("td");
    time.textContent = new Date(e.occurred_at).toLocaleString();
    const stage = document.createElement("td");
    stage.textContent = e.stage;
    const message = document.createElement("td");
    message.className = "diag-msg";
    message.textContent = e.message;
    message.title = e.message;
    tr.append(time, stage, message);
    diagRowsEl.append(tr);
  });
}

function renderGroupButtons() {
  groupsEl.replaceChildren();
  Object.entries(GROUPS).forEach(([key, group]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = group.title;
    button.className = key === state.group ? "active" : "";
    button.addEventListener("click", () => {
      state.group = key;
      state.readings = [];
      renderGroupButtons();
      renderToggles();
      loadReadings();
    });
    groupsEl.append(button);
  });
}

function renderToggles() {
  togglesEl.replaceChildren();
  GROUPS[state.group].fields.forEach((field) => {
    const label = document.createElement("label");
    label.className = "toggle";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = state.enabled.has(field);
    input.addEventListener("change", () => {
      if (input.checked) {
        state.enabled.add(field);
      } else {
        state.enabled.delete(field);
      }
      drawChart();
    });

    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.background = COLORS[field];

    const text = document.createElement("span");
    text.textContent = LABELS[field];

    label.append(input, swatch, text);
    togglesEl.append(label);
  });
}

async function loadReadings() {
  const hours = encodeURIComponent(hoursEl.value);
  const endpoint = state.group === "radiation" ? "/api/radiation" : "/api/readings";

  // 1. Fetch Chart Data (Specific to current tab)
  try {
    const chartRes = await fetch(`${endpoint}?hours=${hours}&max_points=1200`);
    if (chartRes.ok) {
      const payload = await chartRes.json();
      state.readings = payload.readings || [];
      drawChart();
    }
  } catch (err) {
    console.error("Chart load failed:", err);
  }

  // 2. Fetch Latest Metrics (Always fetch both)
  try {
    const [airRes, radRes] = await Promise.allSettled([
      fetch("/api/latest").then(r => r.ok ? r.json() : null),
      fetch("/api/radiation/latest").then(r => r.ok ? r.json() : null)
    ]);

    if (airRes.status === "fulfilled" && airRes.value) {
      state.latestAir = airRes.value.latest;
    }
    if (radRes.status === "fulfilled" && radRes.value) {
      state.latestRad = radRes.value.latest;
    }

    renderDashboard();
  } catch (err) {
    console.error("Metrics load failed:", err);
  }

  const refreshed = new Date().toLocaleTimeString();
  statusEl.textContent = `Updated ${refreshed}`;
}

function renderDashboard() {
  renderLatest();
  renderMetricGrid();
}

function renderLatest() {
  latestEl.replaceChildren();
  const fields = ["score", "temp", "humid", "co2"];
  fields.forEach((field) => {
    const reading = field === "cpm" ? state.latestRad : state.latestAir;
    const item = document.createElement("div");
    item.className = "latest-pill";
    item.innerHTML = `<span class="label">${LABELS[field]}</span><span class="value">${formatValue(reading, field)}</span>`;
    latestEl.append(item);
  });
}

function renderMetricGrid() {
  metricGridEl.replaceChildren();
  Object.values(GROUPS)
    .flatMap((group) => group.fields)
    .forEach((field) => {
      const reading = field === "cpm" ? state.latestRad : state.latestAir;
      const item = document.createElement("div");
      item.className = "metric";
      item.innerHTML = `<span class="label">${LABELS[field]}</span><span class="value">${formatValue(reading, field)}</span>`;
      metricGridEl.append(item);
    });
}

function drawChart() {
  const ratio = window.devicePixelRatio || 1;
  const rect = chart.getBoundingClientRect();
  chart.width = Math.max(320, Math.floor(rect.width * ratio));
  chart.height = Math.max(260, Math.floor(rect.height * ratio));
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

  const width = rect.width;
  const height = rect.height;
  ctx.clearRect(0, 0, width, height);

  const fields = GROUPS[state.group].fields.filter((field) => state.enabled.has(field));
  titleEl.textContent = GROUPS[state.group].title;
  pointCountEl.textContent = `${state.readings.length} points`;

  const padding = { top: 20, right: 30, bottom: 34, left: 30 };
  const plot = {
    x: padding.left,
    y: padding.top,
    w: width - padding.left - padding.right,
    h: height - padding.top - padding.bottom,
  };

  drawFrame(plot);

  if (!state.readings.length || !fields.length) {
    drawEmpty(plot, "No readings for this selection");
    return;
  }

  const values = fields.flatMap((field) =>
    state.readings.map((reading) => reading[field]).filter(Number.isFinite)
  );
  if (!values.length) {
    drawEmpty(plot, "No numeric values");
    return;
  }

  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const pad = (max - min) * 0.08;
  min -= pad;
  max += pad;

  drawYAxis(plot, min, max);
  drawXAxis(plot);

  fields.forEach((field) => drawSeries(plot, field, min, max));
  if (state.mouseX !== null) {
    drawTooltip(plot, fields, min, max, width, height);
  }
}

function drawFrame(plot) {
  ctx.strokeStyle = "#d9e0e8";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.rect(plot.x, plot.y, plot.w, plot.h);
  ctx.stroke();
}

function drawYAxis(plot, min, max) {
  ctx.fillStyle = "#667085";
  ctx.font = "12px system-ui, sans-serif";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  ctx.strokeStyle = "#eef2f6";

  for (let i = 0; i <= 4; i += 1) {
    const value = min + ((max - min) * i) / 4;
    const y = plot.y + plot.h - (plot.h * i) / 4;
    ctx.beginPath();
    ctx.moveTo(plot.x, y);
    ctx.lineTo(plot.x + plot.w, y);
    ctx.stroke();
    ctx.fillText(compactNumber(value), plot.x - 8, y);
  }
}

function drawXAxis(plot) {
  if (!state.readings.length) return;
  const first = new Date(state.readings[0].timestamp);
  const last = new Date(state.readings[state.readings.length - 1].timestamp);
  ctx.fillStyle = "#667085";
  ctx.font = "12px system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.fillText(first.toLocaleString(), plot.x, plot.y + plot.h + 12);
  ctx.textAlign = "right";
  ctx.fillText(last.toLocaleString(), plot.x + plot.w, plot.y + plot.h + 12);
}

function drawSeries(plot, field, min, max) {
  ctx.strokeStyle = COLORS[field];
  ctx.lineWidth = 2;
  ctx.beginPath();
  let started = false;

  state.readings.forEach((reading, index) => {
    const value = reading[field];
    if (!Number.isFinite(value)) return;
    const x = plot.x + (plot.w * index) / Math.max(1, state.readings.length - 1);
    const y = plot.y + plot.h - ((value - min) / (max - min)) * plot.h;
    if (started) {
      ctx.lineTo(x, y);
    } else {
      ctx.moveTo(x, y);
      started = true;
    }
  });

  ctx.stroke();
}

function drawEmpty(plot, message) {
  ctx.fillStyle = "#667085";
  ctx.font = "14px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(message, plot.x + plot.w / 2, plot.y + plot.h / 2);
}

function formatValue(reading, field) {
  if (!reading || !Number.isFinite(reading[field])) return "-";
  const value = reading[field];
  const precision = Math.abs(value) < 100 ? 1 : 0;
  return `${value.toFixed(precision)}${UNITS[field] || ""}`;
}

function compactNumber(value) {
  if (Math.abs(value) >= 1000) {
    return Math.round(value).toLocaleString();
  }
  if (Math.abs(value) >= 100) {
    return value.toFixed(0);
  }
  return value.toFixed(1);
}

function drawTooltip(plot, fields, min, max, width, height) {
  if (!state.readings.length || state.mouseX < plot.x || state.mouseX > plot.x + plot.w) {
    return;
  }

  const index = Math.round(
    ((state.mouseX - plot.x) / plot.w) * (state.readings.length - 1)
  );
  const reading = state.readings[index];
  if (!reading) return;

  const x = plot.x + (plot.w * index) / Math.max(1, state.readings.length - 1);

  // Vertical line
  ctx.strokeStyle = "#94a3b8";
  ctx.setLineDash([4, 4]);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x, plot.y);
  ctx.lineTo(x, plot.y + plot.h);
  ctx.stroke();
  ctx.setLineDash([]);

  // Timestamp
  const date = new Date(reading.timestamp);
  const dateStr = date.toLocaleString();
  ctx.font = "bold 12px system-ui, sans-serif";
  const textWidth = ctx.measureText(dateStr).width;
  const labelWidth = textWidth + 8;
  
  // Clamp X position so the label doesn't go off screen
  const halfWidth = labelWidth / 2;
  const clampedX = Math.max(halfWidth, Math.min(width - halfWidth, x));
  
  ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
  ctx.fillRect(clampedX - halfWidth, plot.y + plot.h + 10, labelWidth, 18);
  
  ctx.fillStyle = "#1e293b";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.fillText(dateStr, clampedX, plot.y + plot.h + 12);

  // Collect points to draw
  const points = fields
    .map((field) => {
      const value = reading[field];
      if (!Number.isFinite(value)) return null;
      return {
        field,
        text: formatValue(reading, field),
        y: plot.y + plot.h - ((value - min) / (max - min)) * plot.h,
      };
    })
    .filter(Boolean)
    .sort((a, b) => a.y - b.y);

  // Adjust Y positions to avoid overlap
  const minSpacing = 20;
  for (let i = 1; i < points.length; i++) {
    if (points[i].y < points[i - 1].y + minSpacing) {
      points[i].y = points[i - 1].y + minSpacing;
    }
  }

  // Draw dots and adjusted labels
  points.forEach((p) => {
    // Dot (always at the original Y intersection)
    const value = reading[p.field];
    const originalY = plot.y + plot.h - ((value - min) / (max - min)) * plot.h;

    ctx.fillStyle = COLORS[p.field];
    ctx.strokeStyle = "white";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x, originalY, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Line connecting dot to adjusted label (if moved)
    if (Math.abs(p.y - originalY) > 1) {
      ctx.strokeStyle = COLORS[p.field];
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 2]);
      ctx.beginPath();
      ctx.moveTo(x, originalY);
      ctx.lineTo(x > plot.x + plot.w / 2 ? x - 5 : x + 5, p.y);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Value text
    ctx.font = "bold 12px system-ui, sans-serif";
    const valWidth = ctx.measureText(p.text).width;
    ctx.textAlign = x > plot.x + plot.w / 2 ? "right" : "left";
    ctx.textBaseline = "middle";
    const offset = x > plot.x + plot.w / 2 ? -10 : 10;

    // Background for legibility
    ctx.fillStyle = "rgba(255, 255, 255, 0.85)";
    const rectX = x > plot.x + plot.w / 2 ? x + offset - valWidth - 4 : x + offset - 4;
    ctx.fillRect(rectX, p.y - 10, valWidth + 8, 20);

    ctx.fillStyle = COLORS[p.field];
    ctx.fillText(p.text, x + offset, p.y);
  });
}

// --- Air conditioner ---------------------------------------------------------
const ac = {
  card: null, power: null, readout: null, cmode: null,
  autoPanel: null, manualPanel: null, targetHum: null, targetTemp: null,
  saveTargets: null, modeBox: null, fanBox: null, view: null,
};

function acInit() {
  ac.card = document.getElementById("ac-card");
  ac.power = document.getElementById("ac-power");
  ac.readout = document.getElementById("ac-readout");
  ac.cmode = document.getElementById("ac-cmode");
  ac.autoPanel = document.getElementById("ac-auto-panel");
  ac.manualPanel = document.getElementById("ac-manual-panel");
  ac.targetHum = document.getElementById("ac-target-hum");
  ac.targetTemp = document.getElementById("ac-target-temp");
  ac.saveTargets = document.getElementById("ac-save-targets");
  ac.modeBox = document.getElementById("ac-mode");
  ac.fanBox = document.getElementById("ac-fan");

  ac.power.addEventListener("click", () => {
    const on = !(ac.view && ac.view.power === "On");
    acPost("/api/ac/power", { on });
  });
  ac.cmode.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-cmode]");
    if (btn) acPost("/api/ac/control-mode", { mode: btn.dataset.cmode });
  });
  ac.saveTargets.addEventListener("click", () => {
    acPost("/api/ac/targets", {
      humidity: Number(ac.targetHum.value),
      temperature: Number(ac.targetTemp.value),
    });
  });
  ac.modeBox.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-mode]");
    if (btn) acPost("/api/ac/mode", { mode: btn.dataset.mode });
  });
  ac.fanBox.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-fan]");
    if (btn) acPost("/api/ac/fan", { speed: btn.dataset.fan });
  });
}

async function loadAc() {
  try {
    const res = await fetch("/api/ac");
    if (!res.ok) return;
    acRender(await res.json());
  } catch (err) {
    console.error("AC load failed:", err);
  }
}

async function acPost(path, payload) {
  try {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const view = await res.json();
    if (res.ok) acRender(view);
    else console.error("AC command failed:", view.error || res.status);
  } catch (err) {
    console.error("AC command failed:", err);
  }
}

function acRender(view) {
  if (!view || !view.available) {
    ac.card.hidden = true;
    return;
  }
  ac.card.hidden = false;
  ac.view = view;

  const on = view.power === "On";
  ac.power.textContent = on ? "On" : "Off";
  ac.power.classList.toggle("on", on);
  ac.power.classList.toggle("off", !on);

  const cur = view.current || {};
  const parts = [];
  if (Number.isFinite(cur.temperature)) parts.push(`Room ${cur.temperature.toFixed(1)} °C`);
  if (Number.isFinite(cur.humidity)) parts.push(`${cur.humidity.toFixed(0)}% RH`);
  if (view.mode) parts.push(`Mode ${view.mode}`);
  if (view.fan_speed) parts.push(`Fan ${view.fan_speed}`);
  ac.readout.textContent = parts.join("  ·  ");

  const auto = view.control_mode === "auto";
  ac.cmode.querySelectorAll("button").forEach((b) =>
    b.classList.toggle("active", b.dataset.cmode === view.control_mode)
  );
  ac.autoPanel.hidden = !auto;
  ac.manualPanel.hidden = auto;

  const t = view.targets || {};
  if (document.activeElement !== ac.targetHum && Number.isFinite(t.humidity)) {
    ac.targetHum.value = t.humidity;
  }
  if (document.activeElement !== ac.targetTemp && Number.isFinite(t.temperature)) {
    ac.targetTemp.value = t.temperature;
  }

  ac.modeBox.querySelectorAll("button").forEach((b) =>
    b.classList.toggle("active", b.dataset.mode === view.mode)
  );
  ac.fanBox.querySelectorAll("button").forEach((b) =>
    b.classList.toggle("active", b.dataset.fan === view.fan_speed)
  );
}

init();
