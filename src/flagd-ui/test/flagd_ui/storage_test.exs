# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUi.StorageTest do
  use ExUnit.Case

  alias FlagdUi.Storage

  describe "Storage server" do
    test "start_link/3" do
      {:ok, _} = start_supervised({Storage, [name: TestedStorage]})

      stop_supervised(TestedStorage)
    end

    test "start_link/3 but already running" do
      {:ok, _} = start_supervised({Storage, [name: TestedStorage]})
      {:error, {:already_started, _}} = start_supervised({Storage, [name: TestedStorage]})

      stop_supervised(TestedStorage)
    end

    test "replace/2 with invalid JSON ignores it and keeps prior state and file content" do
      {:ok, _} = start_supervised({Storage, [name: TestedStorage]})

      file_path = Application.fetch_env!(:flagd_ui, :storage_file_path)
      state_before = GenServer.call(TestedStorage, :read)
      file_content_before = File.read!(file_path)

      GenServer.cast(TestedStorage, {:replace, "not valid json"})

      assert GenServer.call(TestedStorage, :read) == state_before
      assert File.read!(file_path) == file_content_before

      stop_supervised(TestedStorage)
    end
  end
end
