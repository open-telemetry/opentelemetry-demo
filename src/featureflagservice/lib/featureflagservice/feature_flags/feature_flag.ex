# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


defmodule Featureflagservice.FeatureFlags.FeatureFlag do
  use Ecto.Schema
  import Ecto.Changeset

  schema "featureflags" do
    field :description, :string
    field :enabled, :boolean, default: false
    field :name, :string

    timestamps()
  end

  @doc false
  def changeset(feature_flag, attrs) do
    feature_flag
    |> cast(attrs, [:name, :description, :enabled])
    |> validate_required([:name, :description, :enabled])
    |> unique_constraint(:name)
  end
end
