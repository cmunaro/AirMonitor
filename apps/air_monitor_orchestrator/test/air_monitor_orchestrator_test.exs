defmodule AirMonitorOrchestratorTest do
  use ExUnit.Case
  doctest AirMonitorOrchestrator

  test "greets the world" do
    assert AirMonitorOrchestrator.hello() == :world
  end
end
