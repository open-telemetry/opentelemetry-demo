defmodule Chatservice.Repo.Migrations.CreateMessages do
  use Ecto.Migration

  def change do
    create table(:messages) do
      add :topic, :string
      add :name, :string
      add :message, :string
      add :sent_at, :utc_datetime

      timestamps(type: :utc_datetime)
    end
  end
end
