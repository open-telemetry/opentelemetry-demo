defmodule ChatService.ChatContext do
  @moduledoc """
  The database/persistence context
  """

  import Ecto.Query, warn: false
  alias ChatService.Repo

  alias ChatService.ChatContext.Message

  def list_messages(topic) do
    Message
    |> where(topic: ^topic)
    |> Repo.all()
  end

  def create_message(attrs \\ %{}) do
    %Message{}
    |> Message.changeset(attrs)
    |> Repo.insert()
  end
end
