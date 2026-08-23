defmodule AirMonitorCore.AirQualityReading do
  @fields [
    :temp,
    :humid,
    :co2,
    :voc,
    :pm25,
    :pm10,
    :timestamp
  ]

  @enforce_keys @fields
  defstruct @fields

  @type t() :: %__MODULE__{
          temp: float(),
          humid: float(),
          co2: non_neg_integer(),
          voc: non_neg_integer(),
          pm25: non_neg_integer(),
          pm10: non_neg_integer(),
          timestamp: DateTime.t()
        }

  def valid?(%__MODULE__{
        temp: temp,
        humid: humid,
        co2: co2,
        voc: voc,
        pm25: pm25,
        pm10: pm10,
        timestamp: timestamp
      })
      when is_float(temp) and
             is_float(humid) and
             is_integer(co2) and co2 >= 0 and
             is_integer(voc) and voc >= 0 and
             is_integer(pm25) and pm25 >= 0 and
             is_integer(pm10) and pm10 >= 0 and
             is_struct(timestamp, DateTime) do true
  end

  def valid?(_), do: false
end
