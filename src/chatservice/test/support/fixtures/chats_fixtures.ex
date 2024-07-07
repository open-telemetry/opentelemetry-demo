defmodule ChatService.ChatsFixtures do
  @moduledoc """
  This module defines test helpers for creating
  entities via the `Chatservice.Chats` context.
  """

  @doc """
  Generate a message.
  """
  def message_fixture(attrs \\ %{}) do
    {:ok, message} =
      attrs
      |> Enum.into(%{
        topic: "test",
        message: "some message",
        name: "some name",
        sent_at: ~U[2024-07-05 18:28:00Z]
      })
      |> ChatService.ChatContext.create_message()

    message
  end
end
