defmodule AirMonitorWeb.PageControllerTest do
  use AirMonitorWeb.ConnCase

  test "GET /", %{conn: conn} do
    conn = get(conn, ~p"/")
    assert html_response(conn, 200) =~ "Hello world"
  end
end
