# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


defmodule Featureflagservice.FeatureFlagsFixtures do
  @moduledoc """
  This module defines test helpers for creating
  entities via the `Featureflagservice.FeatureFlags` context.
  """

  @doc """
  Generate a unique feature_flag name.
  """
  def unique_feature_flag_name, do: "some name#{System.unique_integer([:positive])}"

  @doc """
  Generate a feature_flag.
  """
  def feature_flag_fixture(attrs \\ %{}) do
    {:ok, feature_flag} =
      attrs
      |> Enum.into(%{
        description: "some description",
        enabled: true,
        name: unique_feature_flag_name()
      })
      |> Featureflagservice.FeatureFlags.create_feature_flag()

    feature_flag
  end
end
