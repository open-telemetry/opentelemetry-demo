# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


defmodule FeatureflagserviceWeb.PageController do
  use FeatureflagserviceWeb, :controller

  alias Featureflagservice.FeatureFlags

  def index(conn, _params) do
    featureflags = FeatureFlags.list_feature_flags()
    render(conn, "index.html", featureflags: featureflags)
  end
end
