defmodule AirMonitorWeb.Application do
  use Application

  @impl true
  def start(_type, _args) do
    children = [
      {Phoenix.PubSub, name: AirMonitorWeb.PubSub},
      AirMonitorWeb.Telemetry,
      AirMonitorWeb.Endpoint
    ]

    Supervisor.start_link(
      children,
      strategy: :one_for_one,
      name: AirMonitorWeb.Supervisor
    )
  end

  @impl true
  def config_change(changed, _new, removed) do
    AirMonitorWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
