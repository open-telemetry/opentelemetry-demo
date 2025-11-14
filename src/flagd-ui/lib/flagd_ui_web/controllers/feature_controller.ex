# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUiWeb.FeatureController do
  use FlagdUiWeb, :controller

  def read(conn, _params) do
    %{"flags" => flags} = GenServer.call(Storage, :read)

    json(conn, %{"flags" => flags})
  end

  def write(conn, %{"data" => data}) do
    payload = Jason.encode!(data)
    GenServer.cast(Storage, {:replace, payload})

    json(conn, %{})
  end
end
