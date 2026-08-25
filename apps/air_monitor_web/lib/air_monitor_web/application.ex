defmodule AirMonitorWeb.Application do
  # See https://elixir.hexdocs.pm/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    children = [
      AirMonitorWeb.Telemetry,
      # Start a worker by calling: AirMonitorWeb.Worker.start_link(arg)
      # {AirMonitorWeb.Worker, arg},
      # Start to serve requests, typically the last entry
      AirMonitorWeb.Endpoint
    ]

    # See https://elixir.hexdocs.pm/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: AirMonitorWeb.Supervisor]
    Supervisor.start_link(children, opts)
  end

  # Tell Phoenix to update the endpoint configuration
  # whenever the application is updated.
  @impl true
  def config_change(changed, _new, removed) do
    AirMonitorWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
