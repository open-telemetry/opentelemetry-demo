defmodule FlagdUi.Application do
  # See https://hexdocs.pm/elixir/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    children = [
      FlagdUiWeb.Telemetry,
      {DNSCluster, query: Application.get_env(:flagd_ui, :dns_cluster_query) || :ignore},
      {Phoenix.PubSub, name: FlagdUi.PubSub},
      # Start a worker by calling: FlagdUi.Worker.start_link(arg)
      # {FlagdUi.Worker, arg},
      # Start to serve requests, typically the last entry
      FlagdUiWeb.Endpoint
    ]

    # See https://hexdocs.pm/elixir/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: FlagdUi.Supervisor]
    Supervisor.start_link(children, opts)
  end

  # Tell Phoenix to update the endpoint configuration
  # whenever the application is updated.
  @impl true
  def config_change(changed, _new, removed) do
    FlagdUiWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
