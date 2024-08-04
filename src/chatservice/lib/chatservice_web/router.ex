defmodule ChatServiceWeb.Router do
  use ChatServiceWeb, :router

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :put_root_layout, html: {ChatServiceWeb.Layouts, :root}
    plug :protect_from_forgery
    plug :put_secure_browser_headers
  end

  # pipeline :api do
  #   plug :accepts, ["json"]
  # end

  scope "/", ChatServiceWeb do
    pipe_through :browser

    get "/", PageController, :home
  end
end
