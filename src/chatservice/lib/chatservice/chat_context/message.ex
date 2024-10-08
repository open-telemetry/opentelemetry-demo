# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
defmodule ChatService.ChatContext.Message do
  @derive {Jason.Encoder, only: [:name, :message, :inserted_at, :topic]}
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key false
  schema "messages" do
    field :topic, :string
    field :name, :string
    field :message, :string

    timestamps(type: :utc_datetime)
  end

  @doc false
  def changeset(message, attrs) do
    message
    |> cast(attrs, [:topic, :name, :message])
    |> validate_required([:topic, :name, :message])
  end
end
