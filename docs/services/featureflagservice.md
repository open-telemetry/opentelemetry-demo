# Feature Flag Service

This service is written in Erlang/Elixir and it is responsible for creating,
reading, updating and deleting feature flags in a PostgreSQL DB.
It is called by Product Catalog and Shipping services.

[Feature Flag Service Source](../../src/featureflagservice/)

## Traces

### Initializing Tracing

In order to set up OpenTelemetry instrumentation for
[Phoenix](https://github.com/open-telemetry/opentelemetry-erlang-contrib/tree/main/instrumentation/opentelemetry_phoenix/),
and
[Ecto](https://github.com/open-telemetry/opentelemetry-erlang-contrib/tree/main/instrumentation/opentelemetry_ecto/),
, we need to call the setup methods of their instrumentation packages before
starting the Supervisor.

This is done in the `application.ex` as follows:

```elixir
@impl true
  def start(_type, _args) do
    OpentelemetryEcto.setup([:featureflagservice, :repo])
    OpentelemetryPhoenix.setup()

    children = [
      # Start the Ecto repository
      Featureflagservice.Repo,
      # Start the PubSub system
      {Phoenix.PubSub, name: Featureflagservice.PubSub},
      # Start the Endpoint (http/https)
      FeatureflagserviceWeb.Endpoint
      # Start a worker by calling: Featureflagservice.Worker.start_link(arg)
      # {Featureflagservice.Worker, arg}
    ]

    # See https://hexdocs.pm/elixir/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: Featureflagservice.Supervisor]
    Supervisor.start_link(children, opts)
  end
```

To add tracing to [grpcbox](https://github.com/tsloughter/grpcbox), we need to
add the appropriate
[interceptor](https://github.com/open-telemetry/opentelemetry-erlang-contrib/tree/main/instrumentation/opentelemetry_grpcbox).

This is configured in the `runtime.exs` file, as follows:

```elixir
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
```

### Add attributes to auto-instrumented spans

Adding attributes to a span is accomplished by using `?set_attribute` on the span
object. In the `get_flag` function two attributes are added to the span.

```elixir
-include_lib("grpcbox/include/grpcbox.hrl").

-include_lib("opentelemetry_api/include/otel_tracer.hrl").

-spec get_flag(ctx:t(), ffs_demo_pb:get_flag_request()) ->
    {ok, ffs_demo_pb:get_flag_response(), ctx:t()} | grpcbox_stream:grpc_error_response().
get_flag(Ctx, #{name := Name}) ->
    case 'Elixir.Featureflagservice.FeatureFlags':get_feature_flag_by_name(Name) of
        nil ->
            {grpc_error, {?GRPC_STATUS_NOT_FOUND, <<"the requested feature flag does not exist">>}};
        #{'__struct__' := 'Elixir.Featureflagservice.FeatureFlags.FeatureFlag',
          description := Description,
          enabled := Enabled,
          inserted_at := CreatedAt,
          updated_at := UpdatedAt
         } ->
            ?set_attribute('app.featureflag.name', Name),
            ?set_attribute('app.featureflag.enabled', Enabled),
            {ok, Epoch} = 'Elixir.NaiveDateTime':from_erl({{1970, 1, 1}, {0, 0, 0}}),
            CreatedAtSeconds = 'Elixir.NaiveDateTime':diff(CreatedAt, Epoch),
            UpdatedAtSeconds = 'Elixir.NaiveDateTime':diff(UpdatedAt, Epoch),
            Flag = #{name => Name,
                     description => Description,
                     enabled => Enabled,
                     created_at => #{seconds => CreatedAtSeconds, nanos => 0},
                     updated_at => #{seconds => UpdatedAtSeconds, nanos => 0}},
            {ok, #{flag => Flag}, Ctx}
    end.
```

## Metrics

TBD

## Logs

TBD
