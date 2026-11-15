# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUiWeb.NavbarTest do
  use FlagdUiWeb.ConnCase

  import Phoenix.LiveViewTest

  test "navigating to the advanced editor live redirects", %{conn: conn} do
    {:ok, view, _html} = live(conn, ~p"/")

    result = view |> element("a", "Advanced") |> render_click()

    assert {:error, {:live_redirect, %{to: "/advanced", kind: :push}}} = result
    assert {:ok, _view, html} = follow_redirect(result, conn, ~p"/advanced")
    assert html =~ "Flagd Configurator"
  end

  test "navigating back to the dashboard live redirects", %{conn: conn} do
    {:ok, view, _html} = live(conn, ~p"/advanced")

    result = view |> element("a", "Basic") |> render_click()

    assert {:error, {:live_redirect, %{to: "/", kind: :push}}} = result
    assert {:ok, _view, html} = follow_redirect(result, conn, ~p"/")
    assert html =~ "Flagd Configurator"
  end
end
