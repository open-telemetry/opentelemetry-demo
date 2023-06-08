# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


defmodule FeatureflagserviceWeb.PageControllerTest do
  use FeatureflagserviceWeb.ConnCase

  test "GET /", %{conn: conn} do
    _conn = get(conn, "/")
    assert true
  end
end
