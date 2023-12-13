defmodule Featureflagservice.Repo.Migrations.CreateFeatureflags do
  use Ecto.Migration

  def change do
    create table(:featureflags) do
      add :name, :string
      add :description, :string
      add :enabled, :float, default: 0.0, null: false

      timestamps()
    end

    create unique_index(:featureflags, [:name])

    execute(&execute_up/0, &execute_down/0)
  end

  defp execute_up do
    repo().insert(%Featureflagservice.FeatureFlags.FeatureFlag{
      name: "productCatalogFailure",
      description: "Fail product catalog service on a specific product",
      enabled: 0.0
    })

    repo().insert(%Featureflagservice.FeatureFlags.FeatureFlag{
      name: "recommendationCache",
      description: "Cache recommendations",
      enabled: 0.0
    })

    repo().insert(%Featureflagservice.FeatureFlags.FeatureFlag{
      name: "adServiceFailure",
      description: "Fail ad service requests sporadically",
      enabled: 0.0
    })

    repo().insert(%Featureflagservice.FeatureFlags.FeatureFlag{
      name: "cartServiceFailure",
      description: "Fail cart service requests sporadically",
      enabled: 0.0
    })
  end

  defp execute_down do
    repo().delete(%Featureflagservice.FeatureFlags.FeatureFlag{name: "productCatalogFailure"})
    repo().delete(%Featureflagservice.FeatureFlags.FeatureFlag{name: "recommendationCache"})
    repo().delete(%Featureflagservice.FeatureFlags.FeatureFlag{name: "adServiceFailure"})
    repo().delete(%Featureflagservice.FeatureFlags.FeatureFlag{name: "cartServiceFailure"})
  end
end
