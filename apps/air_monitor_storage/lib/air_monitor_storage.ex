defmodule AirMonitorStorage do
  require Logger
  @behaviour AirMonitorCore.Storage

  @impl true
  @spec record(AirMonitorCore.scored_readings()) :: :ok | {:error, term}
  def record(scored_readings) do
    %AirMonitorStorage.AirQualityRecord{}
    |> AirMonitorStorage.AirQualityRecord.changeset(scored_readings)
    |> AirMonitorStorage.Repository.insert
    |> inspect
    |> Logger.info
  end

  @impl true
  @spec get_readings() :: [AirMonitorCore.scored_readings()]
  def get_readings() do
    AirMonitorStorage.AirQualityRecord
      |> AirMonitorStorage.Repository.all()
      |> Enum.map(&to_scored_reading/1)
  end

  defp to_scored_reading(%AirMonitorStorage.AirQualityRecord{} = record) do
    %{
      temp: record.temp,
      humid: record.humid,
      co2: record.co2,
      voc: record.voc,
      pm25: record.pm25,
      pm10: record.pm10,
      score: record.score,
      timestamp: record.timestamp
    }
  end
end
