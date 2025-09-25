# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule FlagdUiWeb.AdvancedEditor do
  use FlagdUiWeb, :live_view

  alias FlagdUiWeb.CoreComponents
  alias FlagdUiWeb.Components.Navbar

  def mount(_, _, socket) do
    state = GenServer.call(Storage, :read)
    content = Jason.encode!(state, pretty: true)

    {:ok,
     socket
     |> assign(content: content)
     |> assign(unsaved_changes: false)}
  end

  def render(assigns) do
    ~H"""
    <div class="relative min-h-screen">
      <Navbar.navbar mode="advanced" />

      <CoreComponents.flash kind={:error} flash={@flash} />
      <CoreComponents.flash kind={:info} flash={@flash} />

      <div class="container mx-auto px-4 py-8">
        <.form for={%{}}>
          <textarea
            name="content"
            type="textarea"
            class="mb-4 h-48 w-full bg-gray-700 p-3 text-sm text-gray-300 focus:border-blue-500 focus:outline-none sm:h-64 md:h-80 lg:h-96 xl:h-[32rem] 2xl:h-[48rem]"
            cols={200}
            phx-change="edit"
          >
            {Phoenix.HTML.Form.normalize_value("textarea", @content)}
          </textarea>
          <div>
            <button
              type="button"
              class="rounded bg-blue-500 px-8 py-4 font-medium text-white transition-colors duration-200 hover:bg-blue-600"
              phx-click="save"
            >
              Save
            </button>
            <p :if={@unsaved_changes} class="text-red-600">Unsaved changes</p>
          </div>
        </.form>
      </div>
    </div>
    """
  end

  def handle_event("edit", payload, socket) do
    %{"content" => content} = payload

    {:noreply,
     socket
     |> assign(content: content)
     |> assign(unsaved_changes: true)}
  end

  def handle_event(
        "save",
        _,
        %{
          assigns: %{
            content: content
          }
        } = socket
      ) do
    new_socket =
      case Jason.decode(content) do
        {:ok, _} ->
          trimmed_content = String.trim(content)

          GenServer.cast(Storage, {:replace, trimmed_content})

          socket
          |> assign(unsaved_changes: false)
          |> assign(content: trimmed_content)
          |> clear_flash()
          |> put_flash(:info, "Saved!")

        {:error, _} ->
          put_flash(socket, :error, "Invalid JSON")
      end

    {:noreply, new_socket}
  end
end
