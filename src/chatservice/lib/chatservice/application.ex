defmodule Chatservice.Application do
  # See https://hexdocs.pm/elixir/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    # Set up OpenTelemetry instrumentation
    OpentelemetryPhoenix.setup()
    OpentelemetryEcto.setup([:chatservice, :repo])

    children = [
      ChatserviceWeb.Telemetry,
      Chatservice.Repo,
      {DNSCluster, query: Application.get_env(:chatservice, :dns_cluster_query) || :ignore},
      {Phoenix.PubSub, name: Chatservice.PubSub},
      # Start the Finch HTTP client for sending emails
      {Finch, name: Chatservice.Finch},
      # Start a worker by calling: Chatservice.Worker.start_link(arg)
      # {Chatservice.Worker, arg},
      # Start to serve requests, typically the last entry
      ChatserviceWeb.Endpoint
    ]

    # See https://hexdocs.pm/elixir/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: Chatservice.Supervisor]
    Supervisor.start_link(children, opts)
  end

  # Tell Phoenix to update the endpoint configuration
  # whenever the application is updated.
  @impl true
  def config_change(changed, _new, removed) do
    ChatserviceWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
