module github.com/open-telemetry/opentelemetry-demo/src/load-generator/xk6-otel

go 1.25

require (
	github.com/grafana/sobek v0.0.0-20260429085637-a66d4790012b
	go.k6.io/k6/v2 v2.0.0
	go.opentelemetry.io/otel v1.44.0
	go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc v0.20.0
	go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc v1.44.0
	go.opentelemetry.io/otel/log v0.20.0
	go.opentelemetry.io/otel/sdk v1.44.0
	go.opentelemetry.io/otel/sdk/log v0.20.0
	go.opentelemetry.io/otel/trace v1.44.0
)
