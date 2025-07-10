defmodule FlagdUi.Storage do
  @moduledoc """
  Storage module. This module initializes a process as a separate GenServer
  to linearize reads and writes preventing conflicts and last-writer-wins.
  """

  use GenServer

  def start_link(default) do
    GenServer.start_link(__MODULE__, default)
  end

  @impl true
  def init(state) do
    {:ok, state}
  end

  @impl true
  def handle_call(:read, _from, state) do
    {:reply, nil, state}
  end

  @impl true
  def handle_cast({:write}, state) do
    {:noreply, nil, state}
  end
end
