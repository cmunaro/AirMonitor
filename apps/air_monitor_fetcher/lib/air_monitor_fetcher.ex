defmodule AirMonitorFetcher do
  require Logger

  def fetch do
    Req.get("http://192.168.1.204/air-data/latest")
    |> extract_body()
    |> parse_quality()
    |> deliver_result()
    |> maybe_log_errors()
  end

  defp extract_body({:ok, %Req.Response{body: body}}), do: {:ok, body}
  defp extract_body({:error, _reason} = failure), do: failure

  defp parse_quality({:ok, body}) when is_map(body) do
    with {:ok, timestamp, _offset} <- DateTime.from_iso8601(body["timestamp"]) do
      {:ok, %AirMonitorCore.AirQualityReading{
        temp: body["temp"],
        humid: body["humid"],
        co2: body["co2"],
        voc: body["voc"],
        pm25: body["pm25"],
        pm10: body["pm10_est"],
        timestamp: timestamp
      }}
    else
      {:error, reason} -> {:error, reason}
    end
  end

  defp parse_quality({:ok, _body}), do: {:error, :invalid_response_body}
  defp parse_quality({:error, _reason} = error), do: error

  defp deliver_result(result) do
    case result do
      {:ok, quality} -> AirMonitorCore.ingest(quality)
      {:error, _reason} -> result
    end
  end

  defp maybe_log_errors(result) do
    case result do
      {:error, reason} -> Logger.error("Fetch failed: #{inspect(reason)}")
      :ok -> :ok
    end
  end
end
