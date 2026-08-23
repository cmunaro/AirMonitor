defmodule AirMonitorCoreTest do
  use ExUnit.Case
  doctest AirMonitorCore

  test "greets the world" do
    assert AirMonitorCore.hello() == :world
  end
end
