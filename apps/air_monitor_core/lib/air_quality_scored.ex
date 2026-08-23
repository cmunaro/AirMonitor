defmodule AirMonitorCore.AirQualityScored do
  @fields [
    :details,
    :score
  ]

  @enforce_keys @fields
  defstruct @fields

  @type t() :: %__MODULE__{
          details: %AirMonitorCore.AirQualityReading{},
          score: integer(),
        }

  def valid?(%__MODULE__{
        details: details,
        score: score
      }) do
      AirMonitorCore.AirQualityReading.valid?(details) and
      is_integer(score) and score >= 0
  end

  def valid?(_), do: false
end
