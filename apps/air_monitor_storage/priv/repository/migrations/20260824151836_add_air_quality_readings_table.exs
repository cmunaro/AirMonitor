defmodule AirMonitorStorage.Repository.Migrations.AddAirQualityReadingsTable do
  use Ecto.Migration

  def change do
    create table(:air_quality_readings, primary_key: false) do
      add :timestamp, :utc_datetime_usec,
        primary_key: true,
        null: false

        add :temp, :float, null: false
        add :humid, :float, null: false
        add :co2, :integer, null: false
        add :voc, :integer, null: false
        add :pm25, :integer, null: false
        add :pm10, :integer, null: false
        add :score, :integer, null: false
    end
  end
end
