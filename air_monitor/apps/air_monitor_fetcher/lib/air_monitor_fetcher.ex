defmodule AirMonitorFetcher do
  @moduledoc """
  Documentation for `AirMonitorFetcher`.
  """
  require Logger

  def fetch do
    endpoint = "http://192.168.1.204/air-data/latest"

    case Req.get(endpoint) do
      {:ok, response} ->
        Logger.info(response.body)

      {:error, reason} ->
        Logger.error(reason)
    end
  end
end
