defmodule AirMonitorWeb.Endpoint do
  use Phoenix.Endpoint, otp_app: :air_monitor_web

  @phoenix_static Application.app_dir(:phoenix, "priv/static")
  @live_view_static Application.app_dir(:phoenix_live_view, "priv/static")

  # The session will be stored in the cookie and signed,
  # this means its contents can be read but not tampered with.
  # Set :encryption_salt if you would also like to encrypt it.
  @session_options [
    store: :cookie,
    key: "_air_monitor_web_key",
    signing_salt: "aQNATNah",
    same_site: "Lax"
  ]

  socket "/live", Phoenix.LiveView.Socket,
    websocket: [connect_info: [session: @session_options]],
    longpoll: [connect_info: [session: @session_options]]

  plug Plug.Static,
    at: "/vendor/phoenix",
    from: @phoenix_static,
    only: ~w(phoenix.mjs)

  plug Plug.Static,
    at: "/vendor/phoenix_live_view",
    from: @live_view_static,
    only: ~w(phoenix_live_view.esm.js)

  # Code reloading can be explicitly enabled under the
  # :code_reloader configuration of your endpoint.
  if code_reloading? do
    socket "/phoenix/live_reload/socket", Phoenix.LiveReloader.Socket
    plug Phoenix.LiveReloader
    plug Phoenix.CodeReloader
  end

  plug Phoenix.LiveDashboard.RequestLogger,
    param_key: "request_logger",
    cookie_key: "request_logger"

  plug Plug.RequestId
  plug Plug.Telemetry, event_prefix: [:phoenix, :endpoint]

  plug Plug.Parsers,
    parsers: [:urlencoded, :multipart, :json],
    pass: ["*/*"],
    json_decoder: Phoenix.json_library()

  plug Plug.Session, @session_options
  plug AirMonitorWeb.Router
end
