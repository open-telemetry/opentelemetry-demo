# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUi.Storage do
  @moduledoc """
  Storage module. This module initializes a process as a separate GenServer
  to linearize reads and writes preventing conflicts and last-writer-wins.
  """

  use GenServer
  require Logger

  @file_path Application.compile_env!(:flagd_ui, :storage_file_path)

  def start_link(opts) do
    name = Keyword.get(opts, :name, Storage)

    GenServer.start_link(__MODULE__, %{}, name: name)
  end

  @impl true
  def init(_) do
    state =
      case File.read(@file_path) do
        {:ok, ""} ->
          %{}

        {:ok, content} ->
          case Jason.decode(content) do
            {:ok, parsed} -> parsed
            {:error, _} -> %{}
          end

        {:error, _} ->
          %{}
      end

    Logger.info("Read new state from file")

    {:ok, state}
  end

  @impl true
  def handle_call(:read, _from, state) do
    {:reply, state, state}
  end

  @impl true
  def handle_cast({:replace, json_string}, state) do
    case Jason.decode(json_string) do
      {:ok, new_state} ->
        write_state(json_string)
        {:noreply, new_state}

      {:error, _} ->
        Logger.warning("Ignoring replace with invalid JSON")
        {:noreply, state}
    end
  end

  @impl true
  def handle_cast({:write, flag_name, flag_value}, state) do
    new_state =
      Map.update(state, "flags", %{}, fn flags ->
        update_flag(flags, flag_name, flag_value)
      end)

    json_state = Jason.encode!(new_state, pretty: true)

    write_state(json_state)

    {:noreply, new_state}
  end

  defp update_flag(flags, flag_name, value) do
    flags
    |> Enum.map(fn
      {flag, data} when flag == flag_name ->
        updated_data =
          case get_in(data, ["targeting", "if"]) do
            [_cond, _on, _off] ->
              put_in(
                data,
                ["targeting", "if", Access.at(1)],
                value
              )
            _ ->
              Map.replace(data, "defaultVariant", value)
          end

        {flag, updated_data}
      {flag, data} -> {flag, data}
    end)
    |> Map.new()
  end

  defp write_state(json_string) do
    # Write-then-rename so concurrent readers (e.g. flagd, or another Storage
    # process in tests) never observe a truncated/empty file mid-write:
    # rename/2 is atomic on the same filesystem, plain File.write!/2 is not.
    tmp_path = @file_path <> ".tmp"
    File.write!(tmp_path, json_string)
    File.rename!(tmp_path, @file_path)

    Logger.info("Wrote new state to file")
  end
end
