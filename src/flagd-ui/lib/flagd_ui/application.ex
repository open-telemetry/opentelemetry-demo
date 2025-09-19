# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUi.Application do
  # See https://hexdocs.pm/elixir/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    # Ensure inets is started before OpenTelemetry initialization
    :ok = Application.ensure_started(:inets)

    children = [
      FlagdUiWeb.Telemetry,
      {DNSCluster, query: Application.get_env(:flagd_ui, :dns_cluster_query) || :ignore},
      {Phoenix.PubSub, name: FlagdUi.PubSub},
      FlagdUi.Storage,
      # Start a worker by calling: FlagdUi.Worker.start_link(arg)
      # {FlagdUi.Worker, arg},
      # Start to serve requests, typically the last entry
      FlagdUiWeb.Endpoint
    ]

    OpentelemetryBandit.setup()
    OpentelemetryPhoenix.setup(adapter: :bandit)

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
