defmodule AirMonitorStorage.AirQualityRecord do
  use Ecto.Schema
  import Ecto.Changeset

  @fields [
    :temp,
    :humid,
    :co2,
    :voc,
    :pm25,
    :pm10,
    :score,
    :timestamp
  ]

  @primary_key {:timestamp, :utc_datetime_usec, autogenerate: false}

  schema "air_quality_readings" do
    field :temp, :float
    field :humid, :float
    field :co2, :integer
    field :voc, :integer
    field :pm25, :integer
    field :pm10, :integer
    field :score, :integer
  end

  def changeset(record, attrs) when is_map(attrs) do
    record
    |> cast(attrs, @fields)
    |> validate_required(@fields)
    |> validate_number(:humid,
      greater_than_or_equal_to: 0,
      less_than_or_equal_to: 100
    )
    |> validate_number(:co2, greater_than_or_equal_to: 0)
    |> validate_number(:voc, greater_than_or_equal_to: 0)
    |> validate_number(:pm25, greater_than_or_equal_to: 0)
    |> validate_number(:pm10, greater_than_or_equal_to: 0)
    |> validate_number(:score,
      greater_than_or_equal_to: 0,
      less_than_or_equal_to: 100
    )
  end
end
