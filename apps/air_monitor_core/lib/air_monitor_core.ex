defmodule AirMonitorCore do
  require Logger

  @type scored_readings :: %{
    temp: float(),
    humid: float(),
    co2: non_neg_integer(),
    voc: non_neg_integer(),
    pm25: non_neg_integer(),
    pm10: non_neg_integer(),
    timestamp: DateTime.t(),
    score: non_neg_integer()
  }

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
      |> add_score
      |> AirMonitorCore.Dependencies.storage().record
    else
      Logger.error("Invalid AirQuality #{inspect(reading)}")
    end
  end

  defp add_score(%AirMonitorCore.AirQualityReading{} = reading) do
    readings_map = Map.from_struct(reading)
    Map.put(readings_map, :score, calculate_score(reading))
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

  @spec get_readings :: [scored_readings()]
  def get_readings, do: AirMonitorCore.Dependencies.storage().get_readings()

end
