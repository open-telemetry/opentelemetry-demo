defmodule Featureflagservice.Repo.Migrations.UpdateFeatureFlagsUseFloat do
  use Ecto.Migration

  def change do
    "alter table featureflags alter enabled DROP DEFAULT,alter table featureflags alter enabled type numeric(2,1) using (case when enabled then 1.0 else 0.0 end), alter enabled set default '0.0';"
  end
end
