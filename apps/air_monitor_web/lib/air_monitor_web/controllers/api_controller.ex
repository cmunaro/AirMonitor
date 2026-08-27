defmodule AirMonitorWeb.ApiController do
  use AirMonitorWeb, :controller

  def get_readings(conn, _params) do
    readings = AirMonitorCore.get_readings()
    json(conn, readings)
  end
end

defmodule AirMonitorWeb.ApiJSON do

end
