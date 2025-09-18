# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUiWeb.Components.Navbar do
  use Phoenix.Component
  use FlagdUiWeb, :live_view

  attr :mode, :string, default: "basic", doc: "the view currently displaying"

  def navbar(assigns) do
    ~H"""
    <nav class="bg-gray-800 p-4 sm:p-6">
      <div class="container mx-auto flex items-center justify-between">
        <a href="/feature" class="text-xl font-bold text-white">
          Flagd Configurator
        </a>
        <ul class="flex space-x-2 sm:space-x-4">
          <li>
            <a href="/feature" class={classes("basic", @mode)}>
              Basic
            </a>
          </li>
          <li>
            <a href="/feature/advanced" class={classes("advanced", @mode)}>
              Advanced
            </a>
          </li>
        </ul>
      </div>
    </nav>
    """
  end

  defp classes(route, route),
    do:
      "rounded-md px-3 py-2 text-sm font-medium bg-blue-700 text-white underline underline-offset-4 transition-all duration-200"

  defp classes(_, _),
    do:
      "rounded-md px-3 py-2 text-sm font-medium text-gray-300 hover:bg-gray-700 hover:text-white transition-all duration-200"
end
