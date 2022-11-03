# Email Service

This service will send a confirmation email to the user when an order is placed.

[Email service source](../../src/emailservice/)

## Initializing Tracing

You will need to require the core OpenTelemetry SDK and exporter Ruby gems, as
well as any gem that will be needed for auto-instrumentation libraries
(ie: Sinatra)

```ruby
require "opentelemetry/sdk"
require "opentelemetry/exporter/otlp"
require "opentelemetry/instrumentation/sinatra"
```

The Ruby SDK uses OpenTelemetry standard environment variables to configure
OTLP export, resource attributes, and service name automatically. When
initializing the OpenTelemetry SDK, you will also specify which
auto-instrumentation libraries to leverage (ie: Sinatra)

```ruby
OpenTelemetry::SDK.configure do |c|
  c.use "OpenTelemetry::Instrumentation::Sinatra"
end
```

## Traces

### Add attributes to auto-instrumented spans

Within the execution of auto-instrumented code you can get current span from
context.

```ruby
  current_span = OpenTelemetry::Trace.current_span
```

Adding multiple attributes to a span is accomplished using `add_attributes` on
the span object.

```ruby
  current_span.add_attributes({
    "app.order.id" => data.order.order_id,
  })
```

Adding only a single attribute can be accomplished using `set_attribute` on the
span object.

```ruby
    span.set_attribute("app.email.recipient", data.email)
```

### Create new spans

New spans can be created and placed into active context using `in_span` from an
OpenTelemetry Tracer object. When used in conjunction with a `do..end` block,
the span will automatically be ended when the block ends execution.

```ruby
  tracer = OpenTelemetry.tracer_provider.tracer('emailservice')
  tracer.in_span("send_email") do |span|
    # logic in context of span here
  end
```

## Metrics

TBD

## Logs

TBD
