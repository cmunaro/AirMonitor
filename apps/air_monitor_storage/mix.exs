defmodule AirMonitorStorage.MixProject do
  use Mix.Project

  def project do
    [
      app: :air_monitor_storage,
      version: "0.1.0",
      build_path: "../../_build",
      config_path: "../../config/config.exs",
      deps_path: "../../deps",
      lockfile: "../../mix.lock",
      elixir: "~> 1.20",
      start_permanent: Mix.env() == :prod,
      deps: deps()
    ]
  end

  # Run "mix help compile.app" to learn about applications.
  def application do
    [
      extra_applications: [:logger],
    ]
  end

  # Run "mix help deps" to learn about dependencies.
  defp deps do
    [
      {:air_monitor_core, in_umbrella: true},
      {:ecto_sqlite3, "~> 0.21"}
    ]
  end
end
