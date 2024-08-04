# This file is responsible for configuring your application
# and its dependencies with the aid of the Config module.
#
# This configuration file is loaded before any dependency and
# is restricted to this project.

# General application configuration
import Config

config :chatservice,
  ecto_repos: [ChatService.Repo],
  generators: [timestamp_type: :utc_datetime]

# Configures the endpoint
config :chatservice, ChatServiceWeb.Endpoint,
  url: [host: "localhost"],
  adapter: Bandit.PhoenixAdapter,
  pubsub_server: ChatService.PubSub,
  live_view: [signing_salt: "vhPzRN9o"],
  render_errors: [accepts: ~w(html json), layout: false]

# Configure esbuild (the version is required)
config :esbuild,
  version: "0.17.11",
  chatservice: [
    args:
      ~w(js/app.js --bundle --target=es2017 --outdir=../priv/static/assets --external:/fonts/* --external:/images/*),
    cd: Path.expand("../assets", __DIR__),
    env: %{"NODE_PATH" => Path.expand("../deps", __DIR__)}
  ]

# Configures Elixir's Logger
config :logger, :console,
  format: "$time $metadata[$level] $message\n",
  metadata: [:request_id]

# Use Jason for JSON parsing in Phoenix
config :phoenix, :json_library, Jason

# Configure the OpenTelemetry SDK & Exporter
config :opentelemetry,
  span_processor: :batch,
  traces_exporter: :otlp

# Import environment specific config. This must remain at the bottom
# of this file so it overrides the configuration defined above.
import_config "#{config_env()}.exs"
