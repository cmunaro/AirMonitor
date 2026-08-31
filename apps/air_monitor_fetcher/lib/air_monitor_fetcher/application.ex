defmodule AirMonitorFetcher.Application do
  use Application

  @impl true
  def start(_type, _args) do
    children = [
      AirMonitorFetcher.Worker
    ]

    Supervisor.start_link(
      children,
      strategy: :one_for_one,
      name: AirMonitorFetcher.Supervisor
    )
  end
end
