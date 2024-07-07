defmodule ChatService.ChatServer do
  use GenServer
  alias ChatService.ChatContext

  def start_chat(topic) do
    case Registry.lookup(ChatService.Registry, topic) do
      [] -> start_link(topic)
      [first | _] -> first
    end
  end

  def list_topics() do
    ChatService.Registry
    |> Registry.select([{{:"$1", :_, :_}, [], [{{:"$1"}}]}])
    |> Enum.map(fn {key} -> key end)
  end

  def send_message(topic, message) do
    GenServer.call(via_tuple(topic), {:send_message, Map.put(message, "topic", topic)})
  end

  def get_messages(topic) do
    GenServer.call(via_tuple(topic), :get_messages)
  end

  def start_link(topic) do
    GenServer.start_link(__MODULE__, topic, name: via_tuple(topic))
  end

  @impl true
  def init(topic) do
    messages = ChatContext.list_messages(topic)
    {:ok, messages}
  end

  @impl true
  def handle_call({:send_message, message}, _from, state) do
    saved = ChatContext.create_message(message)
    {:reply, saved, [saved | state]}
  end

  @impl true
  def handle_call(:get_messages, _from, state) do
    {:reply, Enum.reverse(state), state}
  end

  defp via_tuple(topic) do
    {:via, Registry, {ChatService.Registry, topic}}
  end
end
