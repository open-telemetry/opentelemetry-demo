defmodule FeatureflagserviceWeb.Router do
  use FeatureflagserviceWeb, :router

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :put_root_layout, {FeatureflagserviceWeb.LayoutView, :root}
    plug :protect_from_forgery
    plug :put_secure_browser_headers
  end

  pipeline :api do
    plug :accepts, ["json"]
  end

  scope "/", FeatureflagserviceWeb do
    pipe_through :browser

    get "/", PageController, :index
    resources "/featureflags", FeatureFlagController
  end
end
