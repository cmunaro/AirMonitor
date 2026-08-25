defmodule AirMonitorWeb.ErrorJSONTest do
  use AirMonitorWeb.ConnCase, async: true

  test "renders 404" do
    assert AirMonitorWeb.ErrorJSON.render("404.json", %{}) == %{errors: %{detail: "Not Found"}}
  end

  test "renders 500" do
    assert AirMonitorWeb.ErrorJSON.render("500.json", %{}) ==
             %{errors: %{detail: "Internal Server Error"}}
  end
end
