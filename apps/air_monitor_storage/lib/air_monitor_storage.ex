defmodule AirMonitorStorage do
  require Logger
  @behaviour AirMonitorCore.Storage

  @impl true
  @spec record(AirMonitorCore.Storage.scored_readings()) :: :ok | {:error, term}
  def record(scored_readings) do
    %AirMonitorStorage.AirQualityRecord{}
    |> AirMonitorStorage.AirQualityRecord.changeset(scored_readings)
    |> AirMonitorStorage.Repository.insert
    |> inspect
    |> Logger.info
  end

end
