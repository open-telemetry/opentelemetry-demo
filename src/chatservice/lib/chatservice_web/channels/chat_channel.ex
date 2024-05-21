defmodule ChatServiceWeb.ChatChannel do
  use ChatServiceWeb, :channel
  require Logger
  require OpenTelemetry.Tracer
  alias ChatService.ChatServer

  @impl true
  def join(topic, _payload, socket) do
    OpenTelemetry.Tracer.with_span :join do
      ChatServer.start_chat(topic)
      send(self(), :after_join)
      {:ok, assign(socket, :topic, topic)}
    end
  end

  @impl true
  def handle_in("shout", payload, socket) do
    OpenTelemetry.Tracer.with_span :shout do
      ChatServer.send_message(socket.assigns.topic, payload)
      broadcast(socket, "shout", payload)
      {:noreply, socket}
    end
  end

  @impl true
  def handle_info(:after_join, socket) do
    ChatServer.get_messages(socket.assigns.topic)
    |> Enum.each(fn msg -> push(socket, "shout", msg) end)

    {:noreply, socket}
  end
end
