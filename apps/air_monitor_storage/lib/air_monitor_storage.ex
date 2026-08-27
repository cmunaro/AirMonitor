defmodule AirMonitorStorage do
  import Ecto.Query

  @behaviour AirMonitorCore.Storage

  @impl true
  @spec record(AirMonitorCore.scored_reading()) :: :ok | {:error, term()}
  def record(scored_readings) do
    %AirMonitorStorage.AirQualityRecord{}
    |> AirMonitorStorage.AirQualityRecord.changeset(scored_readings)
    |> AirMonitorStorage.Repository.insert
  end

  @impl true
  @spec get_readings(pos_integer(), DateTime.t() | nil) :: AirMonitorCore.readings_page()
  def get_readings(limit, before) when is_integer(limit) and limit > 0 do
    records = AirMonitorStorage.AirQualityRecord
    |> order_by([reading], desc: reading.timestamp)
    |> limit(^(limit + 1)) # Get one more to compute has_more
    |> then(fn query ->
      if before do
        where(query, [reading], reading.timestamp < ^before)
      else query
      end
    end)
    |> AirMonitorStorage.Repository.all

    has_more = length(records) > limit
    page_records = Enum.take(records, limit)

    %{
      data: Enum.map(page_records, &to_scored_reading/1),
      next_cursor: get_next_cursor(page_records, has_more)
    }
  end

  defp get_next_cursor(_records, false), do: nil
  defp get_next_cursor(records, true) do
    records
    |> List.last()
    |> Map.fetch!(:timestamp)
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
