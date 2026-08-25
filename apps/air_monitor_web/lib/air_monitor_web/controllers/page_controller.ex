defmodule AirMonitorWeb.PageController do
  use AirMonitorWeb, :controller

  def home(conn, _params) do
    html(conn, "<!doctype html><html><body>Hello world</body></html>")
  end
end
