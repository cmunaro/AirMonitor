defmodule AirMonitorCore.Application do
  use Application

  @impl true
  def start(_type, _args) do
    children = [
      {Task.Supervisor, name: AirMonitorCore.TaskSupervisor}
    ]

    Supervisor.start_link(
      children,
      strategy: :one_for_one,
      name: AirMonitorCore.Supervisor
    )
  end
end
