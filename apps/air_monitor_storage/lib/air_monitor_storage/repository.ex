defmodule AirMonitorStorage.Repository do
  use Ecto.Repo,
    otp_app: :air_monitor_storage,
    adapter: Ecto.Adapters.SQLite3
end
