defmodule AirMonitorCore.Storage do

  @callback record(AirMonitorCore.scored_reading()) :: :ok | {:error, term()}

  @callback get_readings(pos_integer(), DateTime.t() | nil) :: AirMonitorCore.readings_page()
end
