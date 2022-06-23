defmodule Featureflagservice.FeatureFlags do
  @moduledoc """
  The FeatureFlags context.
  """

  import Ecto.Query, warn: false
  alias Featureflagservice.Repo

  alias Featureflagservice.FeatureFlags.FeatureFlag

  @doc """
  Returns the list of featureflags.

  ## Examples

      iex> list_featureflags()
      [%FeatureFlag{}, ...]

  """
  def list_featureflags do
    Repo.all(FeatureFlag)
  end

  @doc """
  Gets a single feature_flag.

  Raises `Ecto.NoResultsError` if the Feature flag does not exist.

  ## Examples

      iex> get_feature_flag!(123)
      %FeatureFlag{}

      iex> get_feature_flag!(456)
      ** (Ecto.NoResultsError)

  """
  def get_feature_flag!(id), do: Repo.get!(FeatureFlag, id)

  @doc """
  Gets a single feature_flag by name.

  ## Examples

      iex> get_feature_flag_by_name("feature-1")
      %FeatureFlag{}

      iex> get_feature_flag_by_name("not-a-feature-flag")
      nil

  """
  def get_feature_flag_by_name(name), do: Repo.get_by(FeatureFlag, name: name)

  @doc """
  Creates a feature_flag.

  ## Examples

      iex> create_feature_flag(%{field: value})
      {:ok, %FeatureFlag{}}

      iex> create_feature_flag(%{field: bad_value})
      {:error, %Ecto.Changeset{}}

  """
  def create_feature_flag(attrs \\ %{}) do
    %FeatureFlag{}
    |> FeatureFlag.changeset(attrs)
    |> Repo.insert()
  end

  @doc """
  Updates a feature_flag.

  ## Examples

      iex> update_feature_flag(feature_flag, %{field: new_value})
      {:ok, %FeatureFlag{}}

      iex> update_feature_flag(feature_flag, %{field: bad_value})
      {:error, %Ecto.Changeset{}}

  """
  def update_feature_flag(%FeatureFlag{} = feature_flag, attrs) do
    feature_flag
    |> FeatureFlag.changeset(attrs)
    |> Repo.update()
  end

  @doc """
  Deletes a feature_flag.

  ## Examples

      iex> delete_feature_flag(feature_flag)
      {:ok, %FeatureFlag{}}

      iex> delete_feature_flag(feature_flag)
      {:error, %Ecto.Changeset{}}

  """
  def delete_feature_flag(%FeatureFlag{} = feature_flag) do
    Repo.delete(feature_flag)
  end

  @doc """
  Returns an `%Ecto.Changeset{}` for tracking feature_flag changes.

  ## Examples

      iex> change_feature_flag(feature_flag)
      %Ecto.Changeset{data: %FeatureFlag{}}

  """
  def change_feature_flag(%FeatureFlag{} = feature_flag, attrs \\ %{}) do
    FeatureFlag.changeset(feature_flag, attrs)
  end
end
