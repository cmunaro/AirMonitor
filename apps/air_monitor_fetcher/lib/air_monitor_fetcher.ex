defmodule AirMonitorFetcher do
  require Logger

  def fetch do
    Req.get("http://192.168.1.204/air-data/latest")
    |> extract_body()
    |> parse_quality()
    |> deliver_result()
    |> maybe_log_errors()
  end

  defp extract_body({:ok, %Req.Response{body: body}}) do
    {:ok, body}
  end

  defp extract_body({:error, reason}) do
    {:error, {:request_failed, reason}}
  end

  defp parse_quality({:ok, body}) do
    AirMonitorCore.AirQuality.parse(body)
  end

  defp parse_quality({:error, _reason} = error) do
    error
  end


  defp maybe_log_errors(result) do
    case result do
      {:error, reason} -> Logger.error("Fetch failed: #{inspect(reason)}")
      :ok -> :ok
    end
  end

  defp deliver_result({:ok, quality}) do
    AirMonitorCore.ingest(quality)
  end

  defp deliver_result({:error, _} = error) do
    error
  end
end
