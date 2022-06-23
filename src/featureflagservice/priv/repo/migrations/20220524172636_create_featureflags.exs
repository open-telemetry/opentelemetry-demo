defmodule Featureflagservice.Repo.Migrations.CreateFeatureflags do
  use Ecto.Migration

  def change do
    create table(:featureflags) do
      add :name, :string
      add :description, :string
      add :enabled, :boolean, default: false, null: false

      timestamps()
    end

    create unique_index(:featureflags, [:name])
  end
end
