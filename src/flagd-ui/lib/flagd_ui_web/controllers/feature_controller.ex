# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUiWeb.FeatureController do
  use FlagdUiWeb, :controller

  def read(conn, _params) do
    %{"flags" => flags} = GenServer.call(Storage, :read)

    json(conn, %{"flags" => flags})
  end
end
