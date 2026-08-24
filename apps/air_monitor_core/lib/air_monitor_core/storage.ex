defmodule AirMonitorCore.Storage do

  @type scored_readings :: %{
    temp: float(),
    humid: float(),
    co2: non_neg_integer(),
    voc: non_neg_integer(),
    pm25: non_neg_integer(),
    pm10: non_neg_integer(),
    timestamp: DateTime.t(),
    score: non_neg_integer()
  }

  @callback record(scored_readings) :: :ok | {:error, term()}
end
