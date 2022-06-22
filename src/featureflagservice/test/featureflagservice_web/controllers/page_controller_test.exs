defmodule FeatureflagserviceWeb.PageControllerTest do
  use FeatureflagserviceWeb.ConnCase

  test "GET /", %{conn: conn} do
    _conn = get(conn, "/")
    assert true
  end
end
