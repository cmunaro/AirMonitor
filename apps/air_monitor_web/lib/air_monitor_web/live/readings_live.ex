defmodule AirMonitorWeb.ReadingsLive do
  use AirMonitorWeb, :live_view

  @refresh_interval 10_000
  @metrics [
    %{key: :temp, label: "Temperature", unit: "°C", color: "#dc2626"},
    %{key: :humid, label: "Humidity", unit: "%", color: "#0891b2"},
    %{key: :co2, label: "CO₂", unit: "ppm", color: "#16a34a"},
    %{key: :voc, label: "VOC", unit: "", color: "#7c3aed"},
    %{key: :pm25, label: "PM2.5", unit: "µg/m³", color: "#ea580c"},
    %{key: :pm10, label: "PM10", unit: "µg/m³", color: "#ca8a04"},
    %{key: :score, label: "Score", unit: "/100", color: "#2563eb"}
  ]

  @impl true
  def mount(_params, _session, socket) do
    if connected?(socket), do: send(self(), :refresh)

    {:ok, assign(socket, charts: [], reading_count: 0)}
  end

  @impl true
  def handle_info(:refresh, socket) do
    Process.send_after(self(), :refresh, @refresh_interval)
    readings = AirMonitorCore.get_readings(20, nil).data |> Enum.reverse()
    charts = if readings == [], do: [], else: Enum.map(@metrics, &build_chart(&1, readings))

    {:noreply,
     assign(socket,
       charts: charts,
       reading_count: length(readings)
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <main>
      <h1>Air quality</h1>
      <p class="status">
        <%= if @reading_count == 0 do %>
          Waiting for readings…
        <% else %>
          {@reading_count} latest readings
        <% end %>
      </p>

      <div id="charts">
        <section :for={chart <- @charts} class="chart">
          <div class="summary">
            <strong>{chart.label}</strong>
            <span class="latest-value">{chart.latest} {chart.unit}</span>
          </div>
          <svg viewBox="0 0 620 230" role="img" aria-label={"Recent #{chart.label} readings"}>
            <line x1="50" y1="30" x2="50" y2="190" stroke="#cbd5e1" />
            <line x1="50" y1="190" x2="590" y2="190" stroke="#cbd5e1" />
            <text x="8" y="34" fill="#64748b" font-size="12">{chart.maximum}</text>
            <text x="8" y="194" fill="#64748b" font-size="12">{chart.minimum}</text>
            <polyline points={chart.points} fill="none" stroke={chart.color} stroke-width="3" />
            <text x="50" y="216" fill="#64748b" font-size="12">{chart.first_time}</text>
            <text x="590" y="216" fill="#64748b" font-size="12" text-anchor="end">{chart.last_time}</text>
          </svg>
        </section>
      </div>
    </main>
    """
  end

  defp build_chart(metric, readings) do
    values = Enum.map(readings, &Map.fetch!(&1, metric.key))
    {minimum, maximum} = range(values)

    metric
    |> Map.put(:latest, values |> List.last() |> format_number())
    |> Map.put(:minimum, format_number(minimum))
    |> Map.put(:maximum, format_number(maximum))
    |> Map.put(:points, points(values, minimum, maximum))
    |> Map.put(:first_time, readings |> List.first() |> Map.fetch!(:timestamp) |> format_time())
    |> Map.put(:last_time, readings |> List.last() |> Map.fetch!(:timestamp) |> format_time())
  end

  defp range(values) do
    minimum = Enum.min(values)
    maximum = Enum.max(values)

    padding =
      if minimum == maximum,
        do: max(abs(maximum) * 0.05, 1.0),
        else: (maximum - minimum) * 0.1

    {minimum - padding, maximum + padding}
  end

  defp points(values, minimum, maximum) do
    last_index = length(values) - 1

    values
    |> Enum.with_index()
    |> Enum.map_join(" ", fn {value, index} ->
      x = if last_index == 0, do: 310, else: 50 + index * 540 / last_index
      y = 190 - (value - minimum) * 160 / (maximum - minimum)
      "#{x},#{y}"
    end)
  end

  defp format_number(value) when is_integer(value), do: Integer.to_string(value)
  defp format_number(value), do: :erlang.float_to_binary(value * 1.0, decimals: 1)
  defp format_time(timestamp), do: Calendar.strftime(timestamp, "%H:%M:%S")
end
