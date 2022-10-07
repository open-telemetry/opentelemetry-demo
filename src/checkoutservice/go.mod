module github.com/open-telemetry/opentelemetry-demo/src/checkoutservice

go 1.19

require (
	github.com/google/uuid v1.3.0
	github.com/sirupsen/logrus v1.8.1
	go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp v0.32.0
	go.opentelemetry.io/contrib/instrumentation/runtime v0.36.1
	go.opentelemetry.io/otel v1.10.0
	go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc v0.32.1
	go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc v1.10.0
	go.opentelemetry.io/otel/metric v0.32.1
	go.opentelemetry.io/otel/sdk/metric v0.32.1
	go.opentelemetry.io/otel/trace v1.10.0
	google.golang.org/grpc v1.46.2
	google.golang.org/protobuf v1.28.0
)

require (
	cloud.google.com/go/compute v0.1.0 // indirect
	github.com/cenkalti/backoff/v4 v4.1.3 // indirect
	github.com/felixge/httpsnoop v1.0.2 // indirect
	github.com/go-logr/logr v1.2.3 // indirect
	github.com/go-logr/stdr v1.2.2 // indirect
	github.com/golang/protobuf v1.5.2 // indirect
	github.com/grpc-ecosystem/grpc-gateway/v2 v2.7.0 // indirect
	go.opentelemetry.io/otel/exporters/otlp/internal/retry v1.10.0 // indirect
	go.opentelemetry.io/otel/exporters/otlp/otlpmetric v0.32.1 // indirect
	go.opentelemetry.io/proto/otlp v0.19.0 // indirect
	golang.org/x/net v0.0.0-20220121210141-e204ce36a2ba // indirect
)

require (
	go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc v0.32.0
	go.opentelemetry.io/otel/exporters/otlp/otlptrace v1.10.0 // indirect
	go.opentelemetry.io/otel/sdk v1.10.0
	golang.org/x/sys v0.0.0-20220114195835-da31bd327af9 // indirect
	golang.org/x/text v0.3.7 // indirect
	google.golang.org/appengine v1.6.7 // indirect
	google.golang.org/genproto v0.0.0-20220118154757-00ab72f36ad5 // indirect
)
