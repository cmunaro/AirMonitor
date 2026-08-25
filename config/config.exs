# This file is responsible for configuring your umbrella
# and **all applications** and their dependencies with the
# help of the Config module.
#
# Note that all applications in your umbrella share the
# same configuration and dependencies, which is why they
# all use the same configuration file. If you want different
# configurations or dependencies per app, it is best to
# move said applications out of the umbrella.
import Config

config :air_monitor_web,
  generators: [context_app: false]

# Configures the endpoint
config :air_monitor_web, AirMonitorWeb.Endpoint,
  url: [host: "localhost"],
  adapter: Bandit.PhoenixAdapter,
  render_errors: [
    formats: [html: AirMonitorWeb.ErrorHTML, json: AirMonitorWeb.ErrorJSON],
    layout: false
  ],
  pubsub_server: AirMonitorWeb.PubSub,
  live_view: [signing_salt: "zNnUzDsb"]

# Sample configuration:
#
#     config :logger, :default_handler,
#       level: :info
#
#     config :logger, :default_formatter,
#       format: "$date $time [$level] $metadata$message\n",
#       metadata: [:user_id]
#
config :air_monitor_storage,
  ecto_repos: [AirMonitorStorage.Repository]

config :air_monitor_storage, AirMonitorStorage.Repository,
  database: Path.expand("../air_monitor.db", __DIR__),
  pool_size: 1

config :air_monitor_core,
  storage: AirMonitorStorage

import Config

# Configure Elixir's Logger
config :logger, :default_formatter,
  format: "$time $metadata[$level] $message\n",
  metadata: [:request_id]

# Use Jason for JSON parsing in Phoenix
config :phoenix, :json_library, Jason

# Import environment specific config. This must remain at the bottom
# of this file so it overrides the configuration defined above.
import_config "#{config_env()}.exs"
