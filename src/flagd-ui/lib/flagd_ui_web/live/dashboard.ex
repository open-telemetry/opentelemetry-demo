# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUiWeb.Dashboard do
  use FlagdUiWeb, :live_view

  alias FlagdUiWeb.CoreComponents
  alias FlagdUiWeb.Components.Navbar

  def mount(_, _, socket) do
    %{"flags" => flags} = GenServer.call(Storage, :read)
    {:ok, socket |> assign(:flags, flags)}
  end

  def render(assigns) do
    ~H"""
    <div class="relative min-h-screen">
      <Navbar.navbar />

      <CoreComponents.flash kind={:error} flash={@flash} />
      <CoreComponents.flash kind={:info} flash={@flash} />

      <.form for={@flags}>
        <div class="container mx-auto px-4 py-8">
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div
              :for={{name, data} <- @flags}
              class="mb-4 flex flex-auto flex-col justify-between rounded-md bg-gray-800 p-6 text-gray-300 shadow-md"
            >
              <div>
                <p class="mb-4 text-lg font-semibold">{name}</p>
                <p class="-4 text-sm">{data["description"]}</p>
              </div>
              <div>
                <div class="flex items-center justify-between">
                  <CoreComponents.input
                    name={name}
                    type="select"
                    options={get_variants(data)}
                    value={data["defaultVariant"]}
                    phx-change="flag_changed"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </.form>
    </div>
    """
  end

  def handle_event("flag_changed", payload, socket) do
    %{"_target" => [target]} = payload
    variant = payload[target]

    GenServer.cast(Storage, {:write, target, variant})

    new_socket = put_flash(socket, :info, "Saved: #{target}")

    {:noreply, new_socket}
  end

  defp get_variants(%{"variants" => variants}), do: Enum.map(variants, fn {key, _} -> key end)
  defp get_variants(_), do: []
end
