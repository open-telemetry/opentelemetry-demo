defmodule FlagdUi.Storage do
  @moduledoc """
  Storage module. This module initializes a process as a separate GenServer
  to linearize reads and writes preventing conflicts and last-writer-wins.
  """

  use GenServer

  def start_link(_) do
    GenServer.start_link(__MODULE__, %{}, name: Storage)
  end

  @impl true
  def init(_) do
    state = File.cwd!() |> file_path() |> File.read!() |> Jason.decode!()

    {:ok, state}
  end

  @impl true
  def handle_call(:read, _from, state) do
    {:reply, state, state}
  end

  @impl true
  def handle_cast({:write, flag_name, flag_value}, state) do
    {:noreply, nil, state}
  end

  defp file_path(cwd), do: "#{cwd}/data/demo.flagd.json"

  defp update_flag(flags, flag_name, value) do
    flags
    |> Enum.map(fn
      {flag, data} when flag == flag_name -> {flag, Map.replace(data, "defaultVariant", value)}
      {flag, data} -> {flag, data}
    end)
    |> Map.new()
  end
end
