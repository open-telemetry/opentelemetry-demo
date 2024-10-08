# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
defmodule ChatService.ChatServer do
  use GenServer
  alias ChatService.ChatContext
  require OpenTelemetry.Tracer

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
    OpenTelemetry.Tracer.with_span "ChatServer.send_message" do
      current_ctx = OpenTelemetry.Ctx.get_current()
      GenServer.call(via_tuple(topic), {:send_message, Map.put(message, "topic", topic), current_ctx})
    end
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
  def handle_call({:send_message, message, parent_ctx}, _from, state) do
    OpenTelemetry.Ctx.attach(parent_ctx)
    OpenTelemetry.Tracer.with_span :handle_call do
      saved = ChatContext.create_message(message)
      {:reply, saved, [saved | state]}
    end
  end

  @impl true
  def handle_call(:get_messages, _from, state) do
    {:reply, Enum.reverse(state), state}
  end

  defp via_tuple(topic) do
    {:via, Registry, {ChatService.Registry, topic}}
  end
end
