# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUiWeb.SchedulerTest do
  use FlagdUiWeb.ConnCase

  import Phoenix.LiveViewTest

  setup do
    original = GenServer.call(Storage, :read)

    on_exit(fn ->
      FlagdUi.Scheduler.stop_schedule()
      GenServer.cast(Storage, {:replace, Jason.encode!(original)})
    end)

    :ok
  end

  test "renders the schedulable flags and starts out idle", %{conn: conn} do
    {:ok, _view, html} = live(conn, ~p"/scheduler")

    assert html =~ "Scheduler stopped"
    assert html =~ "Idle"
    assert html =~ "adFailure"
    assert html =~ "loadGeneratorVUs"
  end

  test "navigating from the dashboard live redirects", %{conn: conn} do
    {:ok, view, _html} = live(conn, ~p"/")

    result = view |> element("a", "Scheduler") |> render_click()

    assert {:error, {:live_redirect, %{to: "/scheduler", kind: :push}}} = result
    assert {:ok, _view, html} = follow_redirect(result, conn, ~p"/scheduler")
    assert html =~ "Flagd Configurator"
  end

  test "surfaces a validation error for an unusable configuration", %{conn: conn} do
    {:ok, view, _html} = live(conn, ~p"/scheduler")

    html =
      view
      |> form("form",
        interval_seconds: "10",
        min_duration_seconds: "20",
        max_duration_seconds: "30",
        seed: ""
      )
      |> render_submit()

    assert html =~ "must fit within the interval"
    assert html =~ "Scheduler stopped"
  end

  test "rejects a non numeric interval", %{conn: conn} do
    {:ok, view, _html} = live(conn, ~p"/scheduler")

    html =
      view
      |> form("form",
        interval_seconds: "soon",
        min_duration_seconds: "10",
        max_duration_seconds: "20",
        seed: ""
      )
      |> render_submit()

    assert html =~ "whole number of seconds"
  end

  test "starting the scheduler reports it as running", %{conn: conn} do
    {:ok, view, _html} = live(conn, ~p"/scheduler")

    html =
      view
      |> form("form",
        interval_seconds: "600",
        min_duration_seconds: "600",
        max_duration_seconds: "600",
        seed: "7"
      )
      |> render_submit()

    assert html =~ "Scheduler running"
    assert html =~ "Active"

    state = FlagdUi.Scheduler.state()

    assert state.running
    assert state.seed_used == 7
  end

  test "a preset fills in the timing fields", %{conn: conn} do
    {:ok, view, _html} = live(conn, ~p"/scheduler")

    html = view |> element("button", "Presentation") |> render_click()

    assert html =~ ~s(value="60")
    assert html =~ ~s(value="10")
    assert html =~ ~s(value="20")
  end

  test "clearing the flag selection is rejected", %{conn: conn} do
    {:ok, view, _html} = live(conn, ~p"/scheduler")

    view |> element("button", "None") |> render_click()

    html =
      view
      |> form("form",
        interval_seconds: "600",
        min_duration_seconds: "60",
        max_duration_seconds: "120",
        seed: ""
      )
      |> render_submit()

    assert html =~ "at least one flag variant"
  end

  test "offers a checkbox per variant for a flag with several variants", %{conn: conn} do
    {:ok, _view, html} = live(conn, ~p"/scheduler")

    for variant <- ~w(10% 25% 50% 75% 90% 100%) do
      assert html =~ ~s(name="variants[cartFailure][]" value="#{variant}")
    end

    assert html =~ ~s(name="variants[adFailure][]" value="on")
  end

  test "scheduling only the gentle percentages keeps the harsh ones out", %{conn: conn} do
    {:ok, view, _html} = live(conn, ~p"/scheduler")

    view |> element("button", "None") |> render_click()

    view
    |> form("form", %{
      "interval_seconds" => "600",
      "min_duration_seconds" => "600",
      "max_duration_seconds" => "600",
      "seed" => "3",
      "variants" => %{"cartFailure" => ["10%", "25%"]}
    })
    |> render_submit()

    assert FlagdUi.Scheduler.state().config.flags == %{"cartFailure" => ["10%", "25%"]}
  end

  test "toggling a flag clears and restores all of its variants", %{conn: conn} do
    {:ok, view, _html} = live(conn, ~p"/scheduler")

    html = view |> element("button[phx-value-flag='cartFailure']") |> render_click()

    refute html =~ ~s(name="variants[cartFailure][]" value="10%" checked)

    html = view |> element("button[phx-value-flag='cartFailure']") |> render_click()

    assert html =~ ~s(name="variants[cartFailure][]" value="10%" checked)
  end
end
