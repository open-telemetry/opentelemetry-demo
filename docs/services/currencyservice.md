# Currency Service

This service provides functionality to convert amounts between different
currencies.

[Currency service source](../../src/currencyservice/)

## Traces

### Initializing Tracing

The OpenTelemetry SDK is initialized from `main` using the `initTracer`
function defined in `tacer_common.h`

```cpp
void initTracer()
{
  auto exporter = opentelemetry::exporter::otlp::OtlpGrpcExporterFactory::Create();
  auto processor =
      opentelemetry::sdk::trace::SimpleSpanProcessorFactory::Create(std::move(exporter));
  std::vector<std::unique_ptr<opentelemetry::sdk::trace::SpanProcessor>> processors;
  processors.push_back(std::move(processor));
  std::shared_ptr<opentelemetry::sdk::trace::TracerContext> context =
      opentelemetry::sdk::trace::TracerContextFactory::Create(std::move(processors));
  std::shared_ptr<opentelemetry::trace::TracerProvider> provider =
      opentelemetry::sdk::trace::TracerProviderFactory::Create(context);
 // Set the global trace provider
  opentelemetry::trace::Provider::SetTracerProvider(provider);

 // set global propagator
  opentelemetry::context::propagation::GlobalTextMapPropagator::SetGlobalPropagator(
      opentelemetry::nostd::shared_ptr<opentelemetry::context::propagation::TextMapPropagator>(
          new opentelemetry::trace::propagation::HttpTraceContext()));
}
```

### Create new spans

New spans can be created and started using
`Tracer->StartSpan("spanName", attributes, options)`. After a span is created
you need to start and put it into active context using
`Tracer->WithActiveSpan(span)`. You can find an example of this in the `Convert`
function.

```cpp
    std::string span_name = "CurrencyService/Convert";
    auto span =
        get_tracer("currencyservice")->StartSpan(span_name,
                                      {{SemanticConventions::RPC_SYSTEM, "grpc"},
                                       {SemanticConventions::RPC_SERVICE, "CurrencyService"},
                                       {SemanticConventions::RPC_METHOD, "Convert"},
                                       {SemanticConventions::RPC_GRPC_STATUS_CODE, 0}},
                                      options);
    auto scope = get_tracer("currencyservice")->WithActiveSpan(span);
```

### Adding attributes to spans

You can add an attribute to a span using `Span->SetAttribute(key, value)`.

```cpp
    span->SetAttribute("app.currency.conversion.from", from_code);
    span->SetAttribute("app.currency.conversion.to", to_code);
```

### Add span events

Adding span events is accomplished using `Span->AddEvent(name)`.

```cpp
    span->AddEvent("Conversion successful, response sent back");
```

### Set span status

Make sure to set your span status to Ok, or Error accordingly. You can do this
using `Span->SetStatus(status)`

```cpp
    span->SetStatus(StatusCode::kOk);
```

### Tracing context propagation

In C++ propagation is not automatically handled. You need to extract it from the
caller and inject the propagation context into subsequent spans. The
`GrpcServerCarrier` class defines a method to extract context from inbound gRPC
requests which is leveraged in the service call implementations.

The `GrpcServerCarrier` class is defined in `tracer_common.h` as follows:

```cpp
class GrpcServerCarrier : public opentelemetry::context::propagation::TextMapCarrier
{
public:
  GrpcServerCarrier(ServerContext *context) : context_(context) {}
  GrpcServerCarrier() = default;
  virtual opentelemetry::nostd::string_view Get(
      opentelemetry::nostd::string_view key) const noexcept override
  {
    auto it = context_->client_metadata().find(key.data());
    if (it != context_->client_metadata().end())
    {
      return it->second.data();
    }
    return "";
  }

  virtual void Set(opentelemetry::nostd::string_view key,
                   opentelemetry::nostd::string_view value) noexcept override
  {
   // Not required for server
  }

  ServerContext *context_;
};
```

This class is leveraged in the `Convert` method to extract context and create a
`StartSpanOptions` object to contain the right context which is used when
creating new spans.

```cpp
    StartSpanOptions options;
    options.kind = SpanKind::kServer;
    GrpcServerCarrier carrier(context);

    auto prop        = context::propagation::GlobalTextMapPropagator::GetGlobalPropagator();
    auto current_ctx = context::RuntimeContext::GetCurrent();
    auto new_context = prop->Extract(carrier, current_ctx);
    options.parent   = GetSpan(new_context)->GetContext();
```

## Metrics

TBD

## Logs

TBD
