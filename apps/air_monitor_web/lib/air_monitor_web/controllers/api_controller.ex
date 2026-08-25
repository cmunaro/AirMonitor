defmodule AirMonitorWeb.ApiController do
  use AirMonitorWeb, :controller

  def show(conn, params) do
    name = Map.get(params, "name", "default")
    render(conn, :greet, name: name)
  end
end

defmodule AirMonitorWeb.ApiJSON do
  def greet(%{name: name}) do
    %{greeting: "Hello #{name}!"}
  end
end
