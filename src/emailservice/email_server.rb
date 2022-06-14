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
  Pony.mail(
    to:       data.email,
    from:     "noreply@example.com",
    subject:  "Your confirmation email",
    body:     erb(:confirmation, locals: { order: data.order }),
    via:      :logger
  )
end
