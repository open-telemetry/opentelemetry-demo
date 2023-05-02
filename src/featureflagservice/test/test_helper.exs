# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


ExUnit.start()
Ecto.Adapters.SQL.Sandbox.mode(Featureflagservice.Repo, :manual)
