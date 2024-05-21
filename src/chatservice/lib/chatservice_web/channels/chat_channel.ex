defmodule ChatServiceWeb.ChatChannel do
  use ChatServiceWeb, :channel
  require Logger

  @impl true
  def join("chat:lobby", payload, socket) do
    Logger.debug("Socket: " <> inspect(socket))

    if authorized?(payload) do
      {:ok, socket}
    else
      {:error, %{reason: "unauthorized"}}
    end
  end

  # Channels can be used in a request/response fashion
  # by sending replies to requests from the client
  @impl true
  def handle_in("ping", payload, socket) do
    {:reply, {:ok, payload}, socket}
  end

  # It is also common to receive messages from the client and
  # broadcast to everyone in the current topic (chat:lobby).
  @impl true
  def handle_in("shout", payload, socket) do
    broadcast(socket, "shout", payload)
    {:noreply, socket}
  end

  # Add authorization logic here as required.
  defp authorized?(payload) do
    Logger.debug("Join params: " <> inspect(payload))
    true
  end
end
