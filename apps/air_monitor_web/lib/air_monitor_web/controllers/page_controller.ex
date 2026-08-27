defmodule AirMonitorWeb.PageController do
  use AirMonitorWeb, :controller

  def home(conn, _params) do
    html(conn, """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Air Monitor</title>
        <style>
          body {
            margin: 0;
            padding: 2rem;
            background: #f5f7fa;
            color: #172033;
            font-family: system-ui, sans-serif;
          }

          main {
            max-width: 1200px;
            margin: 0 auto;
          }

          #charts {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 1rem;
          }

          .chart {
            padding: 1rem;
            border: 1px solid #dce2ea;
            border-radius: 8px;
            background: white;
          }

          svg {
            display: block;
            width: 100%;
            height: auto;
          }

          .summary {
            display: flex;
            justify-content: space-between;
            margin-bottom: 1rem;
          }

          .latest-value {
            font-size: 1.5rem;
            font-weight: 700;
          }

          #status {
            color: #64748b;
          }
        </style>
      </head>
      <body>
        <main>
          <h1>Air quality</h1>
          <p id="status">Loading…</p>
          <div id="charts"></div>
        </main>

        <script>
          const metrics = [
            {key: "temp", label: "Temperature", unit: "°C", color: "#dc2626"},
            {key: "humid", label: "Humidity", unit: "%", color: "#0891b2"},
            {key: "co2", label: "CO₂", unit: "ppm", color: "#16a34a"},
            {key: "voc", label: "VOC", unit: "", color: "#7c3aed"},
            {key: "pm25", label: "PM2.5", unit: "µg/m³", color: "#ea580c"},
            {key: "pm10", label: "PM10", unit: "µg/m³", color: "#ca8a04"},
            {key: "score", label: "Score", unit: "/100", color: "#2563eb"}
          ];

          const formatTime = timestamp =>
            new Date(timestamp).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});

          const formatValue = value =>
            Number.isInteger(value) ? value : value.toFixed(1);

          function renderChart(metric, readings) {
            const values = readings.map(reading => Number(reading[metric.key]));
            let minimum = Math.min(...values);
            let maximum = Math.max(...values);
            const padding = maximum === minimum ? Math.max(Math.abs(maximum) * 0.05, 1) : (maximum - minimum) * 0.1;
            minimum -= padding;
            maximum += padding;

            const points = values.map((value, index) => {
              const x = values.length === 1 ? 310 : 50 + index * 540 / (values.length - 1);
              const y = 190 - (value - minimum) * 160 / (maximum - minimum);
              return `${x},${y}`;
            }).join(" ");

            return `
              <section class="chart">
                <div class="summary">
                  <strong>${metric.label}</strong>
                  <span class="latest-value">${formatValue(values.at(-1))} ${metric.unit}</span>
                </div>
                <svg viewBox="0 0 620 230" role="img" aria-label="Recent ${metric.label} readings">
                  <line x1="50" y1="30" x2="50" y2="190" stroke="#cbd5e1" />
                  <line x1="50" y1="190" x2="590" y2="190" stroke="#cbd5e1" />
                  <text x="8" y="34" fill="#64748b" font-size="12">${formatValue(maximum)}</text>
                  <text x="8" y="194" fill="#64748b" font-size="12">${formatValue(minimum)}</text>
                  <polyline points="${points}" fill="none" stroke="${metric.color}" stroke-width="3" />
                  <text x="50" y="216" fill="#64748b" font-size="12">${formatTime(readings[0].timestamp)}</text>
                  <text x="590" y="216" fill="#64748b" font-size="12" text-anchor="end">${formatTime(readings.at(-1).timestamp)}</text>
                </svg>
              </section>
            `;
          }

          async function refreshChart() {
            const status = document.getElementById("status");

            try {
              const response = await fetch("/api/readings?limit=20");
              if (!response.ok) throw new Error(`HTTP ${response.status}`);

              const page = await response.json();
              const readings = page.data.slice().reverse();

              if (readings.length === 0) {
                status.textContent = "No readings yet.";
                document.getElementById("charts").innerHTML = "";
                return;
              }

              document.getElementById("charts").innerHTML =
                metrics.map(metric => renderChart(metric, readings)).join("");
              status.textContent = `${readings.length} latest readings`;
            } catch (error) {
              status.textContent = `Could not load readings: ${error.message}`;
            }
          }

          refreshChart();
          setInterval(refreshChart, 5000);
        </script>
      </body>
    </html>
    """)
  end
end
