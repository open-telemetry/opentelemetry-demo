defmodule FlagdUiWeb.AdvancedEditor do
  use FlagdUiWeb, :live_view

  alias FlagdUiWeb.CoreComponents
  alias FlagdUiWeb.Components.Navbar

  def mount(_, _, socket) do
    state = GenServer.call(Storage, :read)
    content = Jason.encode!(state, pretty: true)

    {:ok, socket |> assign(content: content)}
  end

  def render(assigns) do
    ~H"""
    <div class="relative min-h-screen">
      <Navbar.navbar mode="advanced" />
    </div>
    """
  end

  def handle_event("submit", payload, socket) do
    {:noreply, socket}
  end
end
