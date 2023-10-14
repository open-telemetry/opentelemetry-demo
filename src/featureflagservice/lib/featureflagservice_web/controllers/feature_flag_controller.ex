# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


defmodule FeatureflagserviceWeb.FeatureFlagController do
  use FeatureflagserviceWeb, :controller

  alias Featureflagservice.FeatureFlags
  alias Featureflagservice.FeatureFlags.FeatureFlag

  def index(conn, _params) do
    featureflags = FeatureFlags.list_feature_flags()
    render(conn, "index.html", featureflags: featureflags)
  end

  def new(conn, _params) do
    changeset = FeatureFlags.change_feature_flag(%FeatureFlag{})
    render(conn, "new.html", changeset: changeset)
  end

  def create(conn, %{"feature_flag" => feature_flag_params}) do
    case FeatureFlags.create_feature_flag(feature_flag_params) do
      {:ok, feature_flag} ->
        conn
        |> put_flash(:info, "Feature flag created successfully.")
        |> redirect(to: Routes.feature_flag_path(conn, :show, feature_flag))

      {:error, %Ecto.Changeset{} = changeset} ->
        render(conn, "new.html", changeset: changeset)
    end
  end

  def show(conn, %{"id" => id}) do
    feature_flag = FeatureFlags.get_feature_flag!(id)
    render(conn, "show.html", feature_flag: feature_flag)
  end

  def edit(conn, %{"id" => id}) do
    feature_flag = FeatureFlags.get_feature_flag!(id)
    changeset = FeatureFlags.change_feature_flag(feature_flag)
    render(conn, "edit.html", feature_flag: feature_flag, changeset: changeset)
  end

  def update(conn, %{"id" => id, "feature_flag" => feature_flag_params}) do
    feature_flag = FeatureFlags.get_feature_flag!(id)

    case FeatureFlags.update_feature_flag(feature_flag, feature_flag_params) do
      {:ok, feature_flag} ->
        conn
        |> put_flash(:info, "Feature flag updated successfully.")
        |> redirect(to: Routes.feature_flag_path(conn, :show, feature_flag))

      {:error, %Ecto.Changeset{} = changeset} ->
        render(conn, "edit.html", feature_flag: feature_flag, changeset: changeset)
    end
  end

  def delete(conn, %{"id" => id}) do
    feature_flag = FeatureFlags.get_feature_flag!(id)
    {:ok, _feature_flag} = FeatureFlags.delete_feature_flag(feature_flag)

    conn
    |> put_flash(:info, "Feature flag deleted successfully.")
    |> redirect(to: Routes.feature_flag_path(conn, :index))
  end
end
