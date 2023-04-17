# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


defmodule Featureflagservice.Repo do
  use Ecto.Repo,
    otp_app: :featureflagservice,
    adapter: Ecto.Adapters.Postgres
end
