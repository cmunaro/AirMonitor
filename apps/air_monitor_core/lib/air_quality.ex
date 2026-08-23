defmodule AirMonitorCore.AirQuality do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key false
  embedded_schema do
    field(:temp, :float)
    field(:humid, :float)
    field(:co2, :integer)
    field(:voc, :integer)
    field(:pm25, :integer)
    field(:pm10_est, :integer)
    field(:timestamp, :utc_datetime_usec)
  end

  @fields [
    :temp,
    :humid,
    :co2,
    :voc,
    :pm25,
    :pm10_est,
    :timestamp
  ]

  def parse(params) do
    %__MODULE__{}
    |> cast(params, @fields)
    |> validate_required(@fields)
    |> validate_number(:co2, greater_than_or_equal_to: 0)
    |> validate_number(:voc, greater_than_or_equal_to: 0)
    |> validate_number(:pm25, greater_than_or_equal_to: 0)
    |> validate_number(:pm10_est, greater_than_or_equal_to: 0)
    |> apply_action(:parse)
  end
end
