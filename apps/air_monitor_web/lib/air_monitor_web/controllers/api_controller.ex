defmodule AirMonitorWeb.ApiController do
  use AirMonitorWeb, :controller

  def get_readings(conn, params) do
    with {:ok, limit} <- parse_limit(params["limit"]),
         {:ok, before} <- parse_cursor(params["before"]) do
      json(conn, AirMonitorCore.get_readings(limit, before))
    else
      {:error, message} ->
        conn
        |> put_status(:bad_request)
        |> json(%{error: message})
    end
  end

  defp parse_limit(nil), do: {:ok, 20}

  defp parse_limit(value) do
    case Integer.parse(value) do
      {limit, ""} when limit in 1..200 -> {:ok, limit}
      _ -> {:error, "limit must be an integer between 1 and 200"}
    end
  end

  defp parse_cursor(nil), do: {:ok, nil}
  defp parse_cursor(value) do
    case DateTime.from_iso8601(value) do
      {:ok, datetime, _offset} -> {:ok, datetime}
      {:error, _reason} -> {:error, "before must be an ISO 8601 timestamp"}
    end
  end
end

defmodule AirMonitorWeb.ApiJSON do

end
