defmodule AirMonitorWeb.PageController do
  use AirMonitorWeb, :controller

  def home(conn, _params) do
    render(conn, :home)
  end
end
