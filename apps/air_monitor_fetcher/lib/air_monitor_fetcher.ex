defmodule AirMonitorFetcher do
  require Logger

  def fetch do
    Req.get("http://192.168.1.204/air-data/latest")
    |> extract_body()
    |> parse_quality()
    |> log_result()
  end

  defp extract_body({:ok, %Req.Response{status: _status, body: body}}) do
    {:ok, body}
  end

  defp extract_body({:error, reason}) do
    {:error, {:request_failed, reason}}
  end

  defp parse_quality({:ok, body}) do
    AirQuality.parse(body)
  end

  defp parse_quality({:error, _reason} = error) do
    error
  end

  defp log_result({:ok, quality} = result) do
    Logger.info("Air quality: #{inspect(quality)}")
    result
  end

  defp log_result({:error, reason} = error) do
    Logger.error("Fetch failed: #{inspect(reason)}")
    error
  end
end
