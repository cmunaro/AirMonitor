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

  defp parse_quality(result) do
    case result do
      {:ok, body} -> AirMonitorCore.AirQuality.parse(body)
      {:error, _reason} -> result
    end
  end

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
