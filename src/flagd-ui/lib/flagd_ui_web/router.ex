# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUiWeb.Router do
  use FlagdUiWeb, :router

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :put_root_layout, html: {FlagdUiWeb.Layouts, :root}
    plug :protect_from_forgery
    plug :put_secure_browser_headers
  end

  pipeline :api do
    plug :accepts, ["json"]
  end

  scope "/", FlagdUiWeb do
    pipe_through :browser

    live "/", Dashboard
    live "/advanced", AdvancedEditor
  end

  # Other scopes may use custom stacks.
  scope "/api", FlagdUiWeb do
    pipe_through :api

    get "/read", FeatureController, :read
    get "/read-file", FeatureController, :read
    post "/write", FeatureController, :write
    post "/write-to-file", FeatureController, :write
  end

  # Enable LiveDashboard and Swoosh mailbox preview in development
  if Application.compile_env(:flagd_ui, :dev_routes) do
    # If you want to use the LiveDashboard in production, you should put
    # it behind authentication and allow only admins to access it.
    # If your application does not have an admins-only section yet,
    # you can use Plug.BasicAuth to set up some basic authentication
    # as long as you are also using SSL (which you should anyway).
    import Phoenix.LiveDashboard.Router

    scope "/dev" do
      pipe_through :browser

      live_dashboard "/dashboard", metrics: FlagdUiWeb.Telemetry
      forward "/mailbox", Plug.Swoosh.MailboxPreview
    end
  end
end
