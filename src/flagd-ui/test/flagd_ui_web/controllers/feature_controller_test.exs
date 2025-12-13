# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUiWeb.FeatureControllerTest do
  use FlagdUiWeb.ConnCase

  setup do
    file_content = GenServer.call(Storage, :read)

    on_exit(fn ->
      GenServer.cast(Storage, {:replace, Jason.encode!(file_content)})
    end)
  end

  test "GET /api/read", %{conn: conn} do
    conn = get(conn, ~p"/api/read")

    assert %{
             "flags" => %{
               "adFailure" => %{
                 "defaultVariant" => "off",
                 "description" => "Fail ad service",
                 "state" => "ENABLED",
                 "variants" => %{"off" => false, "on" => true}
               },
               "adHighCpu" => %{
                 "defaultVariant" => "off",
                 "description" => "Triggers high cpu load in the ad service",
                 "state" => "ENABLED",
                 "variants" => %{"off" => false, "on" => true}
               }
             }
           } = json_response(conn, 200)
  end

  test "GET /api/read-file (legacy API)", %{conn: conn} do
    conn = get(conn, ~p"/api/read-file")

    assert %{
             "flags" => %{
               "adFailure" => %{
                 "defaultVariant" => "off",
                 "description" => "Fail ad service",
                 "state" => "ENABLED",
                 "variants" => %{"off" => false, "on" => true}
               },
               "adHighCpu" => %{
                 "defaultVariant" => "off",
                 "description" => "Triggers high cpu load in the ad service",
                 "state" => "ENABLED",
                 "variants" => %{"off" => false, "on" => true}
               }
             }
           } = json_response(conn, 200)
  end

  test "POST /api/write", %{conn: conn} do
    data = %{
      "flags" => %{
        "adFailure" => %{
          "defaultVariant" => "off",
          "description" => "Fail ad service",
          "state" => "ENABLED",
          "variants" => %{"off" => true, "on" => false}
        },
        "adHighCpu" => %{
          "defaultVariant" => "off",
          "description" => "Triggers high cpu load in the ad service",
          "state" => "ENABLED",
          "variants" => %{"off" => true, "on" => false}
        }
      }
    }

    conn = post(conn, ~p"/api/write", %{"data" => data})

    conn = get(conn, ~p"/api/read")

    assert %{
             "flags" => %{
               "adFailure" => %{
                 "defaultVariant" => "off",
                 "description" => "Fail ad service",
                 "state" => "ENABLED",
                 "variants" => %{"off" => true, "on" => false}
               },
               "adHighCpu" => %{
                 "defaultVariant" => "off",
                 "description" => "Triggers high cpu load in the ad service",
                 "state" => "ENABLED",
                 "variants" => %{"off" => true, "on" => false}
               }
             }
           } = json_response(conn, 200)
  end

  test "POST /api/write-to-file (legacy API)", %{conn: conn} do
    data = %{
      "flags" => %{
        "adFailure" => %{
          "defaultVariant" => "off",
          "description" => "Fail ad service",
          "state" => "ENABLED",
          "variants" => %{"off" => true, "on" => false}
        },
        "adHighCpu" => %{
          "defaultVariant" => "off",
          "description" => "Triggers high cpu load in the ad service",
          "state" => "ENABLED",
          "variants" => %{"off" => true, "on" => false}
        }
      }
    }

    conn = post(conn, ~p"/api/write-to-file", %{"data" => data})

    conn = get(conn, ~p"/api/read-file")

    assert %{
             "flags" => %{
               "adFailure" => %{
                 "defaultVariant" => "off",
                 "description" => "Fail ad service",
                 "state" => "ENABLED",
                 "variants" => %{"off" => true, "on" => false}
               },
               "adHighCpu" => %{
                 "defaultVariant" => "off",
                 "description" => "Triggers high cpu load in the ad service",
                 "state" => "ENABLED",
                 "variants" => %{"off" => true, "on" => false}
               }
             }
           } = json_response(conn, 200)
  end
end
