defmodule Featureflagservice.Release do
  @moduledoc """
  Used for executing DB release tasks when run in production without Mix
  installed.
  """
  @app :featureflagservice

  def migrate do
    load_app()

    # Migrations don't always run on startup because the Postgres database may not be completely ready
    # TODO: check for database connection instead of 5 second sleep
    IO.puts "Waiting 5 seconds for database to start..."
    Process.sleep(5000)

    for repo <- repos() do
      {:ok, _, _} = Ecto.Migrator.with_repo(repo, &Ecto.Migrator.run(&1, :up, all: true))
    end
  end

  def rollback(repo, version) do
    load_app()
    {:ok, _, _} = Ecto.Migrator.with_repo(repo, &Ecto.Migrator.run(&1, :down, to: version))
  end

  defp repos do
    Application.fetch_env!(@app, :ecto_repos)
  end

  defp load_app do
    Application.load(@app)
  end
end
