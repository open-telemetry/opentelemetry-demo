defmodule FeatureflagserviceWeb.PageController do
  use FeatureflagserviceWeb, :controller

  alias Featureflagservice.FeatureFlags
  alias Featureflagservice.FeatureFlags.FeatureFlag

  def index(conn, _params) do
    featureflags = FeatureFlags.list_featureflags()
    render(conn, "index.html", featureflags: featureflags)
  end
end
