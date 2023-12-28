# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

defmodule Featureflagservice.FeatureFlags.FeatureFlag do
  use Ecto.Schema
  import Ecto.Changeset

  schema "featureflags" do
    field :description, :string
    field :enabled, :float, default: 0.0
    field :name, :string

    timestamps()
  end

  @doc false
  def changeset(feature_flag, attrs) do
    feature_flag
    |> cast(attrs, [:name, :description, :enabled])
    |> validate_required([:name, :description, :enabled])
    |> validate_number(:enabled, greater_than_or_equal_to: 0.0, less_than_or_equal_to: 1.0)
    |> unique_constraint(:name)
  end
end
