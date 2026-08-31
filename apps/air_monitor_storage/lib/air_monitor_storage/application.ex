defmodule AirMonitorStorage.Application do
  use Application

  @impl true
  def start(_type, _args) do
    children = [
      AirMonitorStorage.Repository
    ]

    Supervisor.start_link(
      children,
      strategy: :one_for_one,
      name: AirMonitorStorage.Supervisor
    )
  end
end
