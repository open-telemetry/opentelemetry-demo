# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule Featureflagservice.FeatureFlags.FeatureFlag do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:name, :string, autogenerate: false}
  @derive {Phoenix.Param, key: :name}

  schema "featureflags"  do
    field :description, :string
    field :enabled, :float, default: 0.0
  end

  @doc false
  def changeset(feature_flag, attrs) do
    feature_flag
    |> cast(attrs, [:name, :description, :enabled])
    |> validate_required([:name, :description, :enabled])
    |> unique_constraint(:name)
  end
end
