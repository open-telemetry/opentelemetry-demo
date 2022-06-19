require "ostruct"
require "pony"
require "sinatra"

require "opentelemetry/sdk"
require "opentelemetry/exporter/otlp"
require "opentelemetry/instrumentation/sinatra"

OpenTelemetry::SDK.configure do |c|
  c.use "OpenTelemetry::Instrumentation::Sinatra"
end

post "/send_order_confirmation" do
  data = JSON.parse(request.body.read, object_class: OpenStruct)

  # get the current auto-instrumented span
  current_span = OpenTelemetry::Trace.current_span
  current_span.add_attributes({
    "app.order.id" => data.order.order_id,
    "app.shipping.tracking.id" => data.order.shipping_tracking_id,
    "app.shipping.cost.currency" => data.order.shipping_cost.currency_code,
    "app.shipping.cost" => data.order.shipping_cost.units.to_s + "." + 
      data.order.shipping_cost.nanos.to_s
  })

  send_email(data)

  rescue Exception => e
    # record exception in span (will create a span event)
    current_span.record_exception(e)
    raise e
end

def send_email(data)
  # create and start a manual span
  tracer = OpenTelemetry.tracer_provider.tracer('')
  tracer.in_span("send_email") do |span|
    Pony.mail(
      to:       data.email,
      from:     "noreply@example.com",
      subject:  "Your confirmation email",
      body:     erb(:confirmation, locals: { order: data.order }),
      via:      :logger
    )
    span.set_attribute("app.email.sent", true)
  end
  # manually created spans need to be ended
  # in Ruby, the method `in_span` ends it automatically
  # check out the OpenTelemetry Ruby docs at: 
  # https://opentelemetry.io/docs/instrumentation/ruby/manual/#creating-new-spans 
end
