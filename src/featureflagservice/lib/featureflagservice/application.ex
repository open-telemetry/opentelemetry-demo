defmodule Featureflagservice.Application do
  # See https://hexdocs.pm/elixir/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    OpentelemetryEcto.setup([:featureflagservice, :repo])
    OpentelemetryPhoenix.setup()

    children = [
      # Start the Ecto repository
      Featureflagservice.Repo,
      # Start the PubSub system
      {Phoenix.PubSub, name: Featureflagservice.PubSub},
      # Start the Endpoint (http/https)
      FeatureflagserviceWeb.Endpoint
      # Start a worker by calling: Featureflagservice.Worker.start_link(arg)
      # {Featureflagservice.Worker, arg}
    ]

    # See https://hexdocs.pm/elixir/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: Featureflagservice.Supervisor]
    Supervisor.start_link(children, opts)
  end

  # Tell Phoenix to update the endpoint configuration
  # whenever the application is updated.
  @impl true
  def config_change(changed, _new, removed) do
    FeatureflagserviceWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
