defmodule AirMonitorCore.Storage do

  @callback record(AirMonitorCore.scored_readings) :: :ok | {:error, term()}

  @callback get_readings() :: [AirMonitorCore.scored_readings()]
end
