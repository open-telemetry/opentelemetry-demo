defmodule ChatService.ChatContext.Message do
  @derive {Jason.Encoder, only: [:name, :message, :inserted_at, :topic]}
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key false
  schema "messages" do
    field :topic, :string
    field :name, :string
    field :message, :string

    timestamps(type: :utc_datetime)
  end

  @doc false
  def changeset(message, attrs) do
    message
    |> cast(attrs, [:topic, :name, :message])
    |> validate_required([:topic, :name, :message])
  end
end
