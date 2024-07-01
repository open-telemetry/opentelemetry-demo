defmodule ChatService.Repo do
  use Ecto.Repo,
    otp_app: :chatservice,
    adapter: Ecto.Adapters.Postgres
end
