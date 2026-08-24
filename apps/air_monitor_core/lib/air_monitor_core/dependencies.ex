defmodule AirMonitorCore.Dependencies do

  def storage do
    Application.fetch_env!(:air_monitor_core, :storage)
  end
end
