import Config

if System.get_env("PHX_SERVER") do
  config :featureflagservice, FeatureflagserviceWeb.Endpoint, server: true
end

grpc_port = String.to_integer(System.get_env("FEATURE_FLAG_GRPC_SERVICE_PORT") || "50053")

config :grpcbox,
  servers: [
    %{
      :grpc_opts => %{
        :service_protos => [:ffs_demo_pb],
        :unary_interceptor => {:otel_grpcbox_interceptor, :unary},
        :services => %{:"hipstershop.FeatureFlagService" => :ffs_service}
      },
      :listen_opts => %{:port => grpc_port}
    }
  ]

if config_env() == :prod do
  database_url =
    System.get_env("DATABASE_URL") ||
      raise """
      environment variable DATABASE_URL is missing.
      For example: ecto://USER:PASS@HOST/DATABASE
      """

  maybe_ipv6 = if System.get_env("ECTO_IPV6"), do: [:inet6], else: []

  config :featureflagservice, Featureflagservice.Repo,
    # ssl: true,
    url: database_url,
    pool_size: String.to_integer(System.get_env("POOL_SIZE") || "10"),
    socket_options: maybe_ipv6

  # The secret key base is used to sign/encrypt cookies and other secrets.
  # A default value is used in config/dev.exs and config/test.exs but you
  # want to use a different value for prod and you most likely don't want
  # to check this value into version control, so we use an environment
  # variable instead.
  #
  # A default value is provided to simplify the creation of new demos, but
  # this practice should not be used in actual user-facing applications.
  secret_key_base =
    System.get_env("SECRET_KEY_BASE") || "GH1AJrEOJEVmzyUE+5kgz2cfBEOg5qPBlTYVive++6s/QS0BE3xjNoRCd7xI3zSv" 

  host = System.get_env("PHX_HOST") || "localhost"
  port = String.to_integer(System.get_env("FEATURE_FLAG_SERVICE_PORT") || "8081")

  config :featureflagservice, FeatureflagserviceWeb.Endpoint,
    url: [host: host, port: 443, scheme: "https"],
    http: [
      ip: {0, 0, 0, 0},
      port: port
    ],
    secret_key_base: secret_key_base
end
