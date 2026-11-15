# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import Config

# We don't run a server during test. If one is required,
# you can enable the server option below.
config :flagd_ui, FlagdUiWeb.Endpoint,
  url: [path: "/"],
  http: [ip: {127, 0, 0, 1}, port: 4002],
  secret_key_base: "7WKq9+4aRwQEUAE69h03WLZKqkUmgMOlrrXvsq28ZvKNK9HSinOQ3ZBcnUG/eSgb",
  server: false

# In test we don't send emails
config :flagd_ui, FlagdUi.Mailer, adapter: Swoosh.Adapters.Test

# Disable swoosh api client as it is only required for production adapters
config :swoosh, :api_client, false

# Print only warnings and errors during test
config :logger, level: :warning

# Initialize plugs at runtime for faster test compilation
config :phoenix, :plug_init_mode, :runtime

# Enable helpful, but potentially expensive runtime checks
config :phoenix_live_view,
  enable_expensive_runtime_checks: true

storage_file_path = Path.expand("../tmp/demo.flagd.json", __DIR__)
fixture_path = Path.expand("../../flagd/demo.flagd.json", __DIR__)

File.mkdir_p!(Path.dirname(storage_file_path))
_ = File.rm(storage_file_path)
File.cp!(fixture_path, storage_file_path)

config :flagd_ui, storage_file_path: storage_file_path
