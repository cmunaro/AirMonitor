defmodule AirMonitorCore do
  require Logger

  def ingest(%AirMonitorCore.AirQualityReading{} = data) do
    case Task.Supervisor.start_child(
      AirMonitorCore.TaskSupervisor,
      fn -> process(data) end
    ) do
      {:ok, _pid} -> :ok
      {:error, reason} -> {:error, reason}
    end
  end

  defp process(%AirMonitorCore.AirQualityReading{} = reading) do
    if AirMonitorCore.AirQualityReading.valid?(reading) do
      reading
      |> to_scored_quality()
      # Save into db from storage app
      |> Logger.info
    else
      Logger.error("Invalid AirQuality #{inspect(reading)}")
    end
  end

  defp to_scored_quality(%AirMonitorCore.AirQualityReading{} = air_quality) do
    %AirMonitorCore.AirQualityScored{
      details: air_quality,
      score: calculate_score(air_quality)
    }
  end

  defp calculate_score(%AirMonitorCore.AirQualityReading{} = air_quality) do
    [
    {air_quality.co2, 400, 2_000, 0.35},
    {air_quality.voc, 0, 500, 0.20},
    {air_quality.pm25, 0, 100, 0.30},
    {air_quality.pm10, 0, 200, 0.15}
  ]
  |> Enum.reduce(0.0, fn {value, good, bad, weight}, total ->
    normalized = ((value - good) / (bad - good))
      |> max(0.0)
      |> min(1.0)
    component_score = 100.0 * (1.0 - normalized * normalized)
    total + component_score * weight
  end)
  |> round()
  |> max(0)
  |> min(100)
  end

end
