# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require "ostruct"
require "pony"
require "sinatra"

require "opentelemetry/sdk"
require "opentelemetry/exporter/otlp"
require "opentelemetry/instrumentation/all"

require "bugsnag_performance"

set :port, ENV["EMAIL_PORT"]

BugsnagPerformance.configure do |c|
  c.api_key = ENV["BUGSNAG_API_KEY"]
  c.app_version = ENV["BUGSNAG_APP_VERSION"]
  c.release_stage = ENV["BUGSNAG_RELEASE_STAGE"]

  c.configure_open_telemetry do |otel_c|
    otel_c.use_all
  end
end

post "/send_order_confirmation" do
  data = JSON.parse(request.body.read, object_class: OpenStruct)

  # get the current auto-instrumented span
  current_span = OpenTelemetry::Trace.current_span
  current_span.add_attributes({
    "app.order.id" => data.order.order_id,
  })

  send_email(data)

end

error do
  OpenTelemetry::Trace.current_span.record_exception(env['sinatra.error'])
end

def send_email(data)
  # create and start a manual span
  tracer = OpenTelemetry.tracer_provider.tracer('email')
  tracer.in_span("send_email") do |span|
    Pony.mail(
      to:       data.email,
      from:     "noreply@example.com",
      subject:  "Your confirmation email",
      body:     erb(:confirmation, locals: { order: data.order }),
      via:      :test
    )

    # mark this span as "first class" so that it is aggregated in the bugsnag dashboard
    span.set_attribute("bugsnag.span.first_class", true)
    span.set_attribute("app.email.recipient", data.email)

    puts "Order confirmation email sent to: #{data.email}"
  end
  # manually created spans need to be ended
  # in Ruby, the method `in_span` ends it automatically
  # check out the OpenTelemetry Ruby docs at: 
  # https://opentelemetry.io/docs/instrumentation/ruby/manual/#creating-new-spans 
end
