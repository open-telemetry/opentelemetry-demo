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
    OpenTelemetry.Tracer.with_span :shout, %{kind: :consumer} do
      OpenTelemetry.Tracer.set_attributes(%{
        "messaging.operation.name": :shout,
        "messaging.destination.name": socket.assigns.topic,
        "messaging.message.body.size": byte_size(:erlang.term_to_binary(payload))
      })
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
