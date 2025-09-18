# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

[
  import_deps: [:phoenix],
  plugins: [Phoenix.LiveView.HTMLFormatter],
  inputs: ["*.{heex,ex,exs}", "{config,lib,test}/**/*.{heex,ex,exs}"]
]
