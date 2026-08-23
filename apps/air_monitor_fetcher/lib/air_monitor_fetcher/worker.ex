defmodule AirMonitorFetcher.Worker do
  use GenServer

  def start_link(opts \\ []) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  @impl true
  def init(_opts) do
    send(self(), :fetch)
    {:ok, nil}
  end

  @impl true
  def handle_info(:fetch, state) do
    AirMonitorFetcher.fetch()
    Process.send_after(self(), :fetch, 10_000)
    {:noreply, state}
  end

end
