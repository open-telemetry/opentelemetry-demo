defmodule ChatService.ChatServer do
  require OpenTelemetry.Tracer

  def start_chat(topic) do
    case Registry.lookup(ChatService.Registry, topic) do
      [] -> start_link(topic)
      [first | _] -> first
    end
  end

  def start_link(topic) do
    GenServer.start_link(__MODULE__, %{}, name: via_tuple(topic))
  end

  def list_topics() do
    ChatService.Registry
    |> Registry.select([{{:"$1", :_, :_}, [], [{{:"$1"}}]}])
    |> Enum.map(fn {key} -> key end)
  end

  def send_message(topic, message) do
    OpenTelemetry.Tracer.with_span :send_message do
      GenServer.call(via_tuple(topic), {:send_message, message})
    end
  end

  def get_messages(topic) do
    GenServer.call(via_tuple(topic), :get_messages)
  end

  def init(_) do
    {:ok, []}
  end

  def handle_call({:send_message, message}, _from, state) do
    {:reply, :ok, [message | state]}
  end

  def handle_call(:get_messages, _from, state) do
    {:reply, Enum.reverse(state), state}
  end

  defp via_tuple(topic) do
    {:via, Registry, {ChatService.Registry, topic}}
  end
end
