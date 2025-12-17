# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUi.MixProject do
  use Mix.Project

  def project do
    [
      app: :flagd_ui,
      version: "0.1.1",
      elixir: "~> 1.19",
      elixirc_paths: elixirc_paths(Mix.env()),
      start_permanent: Mix.env() == :prod,
      aliases: aliases(),
      deps: deps(),
      releases: [
        flagd_ui: [
          applications: [
            opentelemetry_exporter: :permanent,
            opentelemetry: :temporary
          ]
        ]
      ]
    ]
  end

  # Configuration for the OTP application.
  #
  # Type `mix help compile.app` for more information.
  def application do
    [
      mod: {FlagdUi.Application, []},
      extra_applications: [:logger, :runtime_tools]
    ]
  end

  # Specifies which paths to compile per environment.
  defp elixirc_paths(:test), do: ["lib", "test/support"]
  defp elixirc_paths(_), do: ["lib"]

  # Specifies your project dependencies.
  #
  # Type `mix help deps` for examples and options.
  defp deps do
    [
      {:phoenix, "~> 1.8.1", override: true},
      {:phoenix_html, "~> 4.3.0"},
      {:phoenix_live_reload, "~> 1.6.1", only: :dev},
      {:phoenix_live_view, "~> 1.1.18"},
      {:floki, "~> 0.38.0", only: :test},
      {:phoenix_live_dashboard, "~> 0.8.7"},
      {:esbuild, "~> 0.10.0", runtime: Mix.env() == :dev},
      {:tailwind, "~> 0.4.1", runtime: Mix.env() == :dev},
      {:heroicons,
       github: "tailwindlabs/heroicons",
       tag: "v2.2.0",
       sparse: "optimized",
       app: false,
       compile: false,
       depth: 1},
      {:swoosh, "~> 1.19.8"},
      {:req, "~> 0.5.16"},
      {:telemetry_metrics, "~> 1.1.0"},
      {:telemetry_poller, "~> 1.3.0"},
      {:gettext, "~> 1.0.2"},
      {:jason, "~> 1.4.4"},
      {:dns_cluster, "~> 0.2.0"},
      {:bandit, "~> 1.9.0"},
      {:credo, "~> 1.7.13", only: [:dev, :test], runtime: false},
      {:opentelemetry, "~> 1.7.0"},
      {:opentelemetry_api, "~> 1.5.0"},
      {:opentelemetry_exporter, "~> 1.10.0"},
      {:opentelemetry_phoenix, "~> 2.0.1"},
      {:opentelemetry_bandit, "~> 0.3.0"}
    ]
  end

  # Aliases are shortcuts or tasks specific to the current project.
  # For example, to install project dependencies and perform other setup tasks, run:
  #
  #     $ mix setup
  #
  # See the documentation for `Mix` for more info on aliases.
  defp aliases do
    [
      setup: ["deps.get", "assets.setup", "assets.build"],
      "assets.setup": ["tailwind.install --if-missing", "esbuild.install --if-missing"],
      "assets.build": ["tailwind flagd_ui", "esbuild flagd_ui"],
      "assets.deploy": [
        "tailwind flagd_ui --minify",
        "esbuild flagd_ui --minify",
        "phx.digest"
      ]
    ]
  end
end
