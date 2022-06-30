defmodule Featureflagservice.Repo do
  use Ecto.Repo,
    otp_app: :featureflagservice,
    adapter: Ecto.Adapters.Postgres
end
