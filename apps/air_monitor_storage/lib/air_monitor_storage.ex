defmodule AirMonitorStorage do
  require Logger

  def record(scored_readings) when is_map(scored_readings) do
    %AirMonitorStorage.AirQualityRecord{}
    |> AirMonitorStorage.AirQualityRecord.changeset(scored_readings)
    |> AirMonitorStorage.Repository.insert
    |> inspect
    |> Logger.info
  end

end
