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
  end
end
