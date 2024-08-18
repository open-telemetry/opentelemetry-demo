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
defmodule ChatService.ChatsTest do
  use ChatService.DataCase

  alias ChatService.ChatContext

  describe "messages" do
    alias ChatService.ChatContext.Message

    import ChatService.ChatsFixtures

    @invalid_attrs %{topic: nil, message: nil, name: nil, sent_at: nil}

    test "list_messages/0 returns all messages for topic" do
      message = message_fixture()
      assert ChatContext.list_messages(message.topic) == [message]
    end

    test "create_message/1 with valid data creates a message" do
      valid_attrs = %{
        topic: "josh",
        message: "some message",
        name: "some name",
        sent_at: ~U[2024-07-05 18:28:00Z]
      }

      assert {:ok, %Message{} = message} = ChatContext.create_message(valid_attrs)
      assert message.message == "some message"
      assert message.name == "some name"
      assert message.sent_at == ~U[2024-07-05 18:28:00Z]
    end

    test "create_message/1 with invalid data returns error changeset" do
      assert {:error, %Ecto.Changeset{}} = ChatContext.create_message(@invalid_attrs)
    end
  end
end
