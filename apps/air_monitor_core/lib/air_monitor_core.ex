defmodule AirMonitorCore do
  require Logger

  def ingest(%AirMonitorCore.AirQuality{} = data) do
    case Task.Supervisor.start_child(
      AirMonitorCore.TaskSupervisor,
      fn -> process(data) end
    ) do
      {:ok, _pid} -> :ok
      {:error, reason} -> {:error, reason}
    end
  end

  defp process(%AirMonitorCore.AirQuality{} = data) do
    Logger.info(inspect(data))
    # Calculate score
    # Save into db from storage app
  end

end
