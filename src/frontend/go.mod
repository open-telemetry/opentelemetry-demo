module github.com/GoogleCloudPlatform/microservices-demo/src/frontend

go 1.17

require (
	cloud.google.com/go/compute v1.5.0
	github.com/google/uuid v1.3.0
	github.com/gorilla/mux v1.8.0
	github.com/pkg/errors v0.9.1
	github.com/sirupsen/logrus v1.8.1
	go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc v0.29.0
	go.opentelemetry.io/otel v1.4.1
	go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc v1.4.1
	go.opentelemetry.io/otel/sdk v1.4.1
	google.golang.org/grpc v1.44.0
)

require (
	github.com/cenkalti/backoff/v4 v4.1.2 // indirect
	github.com/felixge/httpsnoop v1.0.2 // indirect
	github.com/go-logr/logr v1.2.2 // indirect
	github.com/go-logr/stdr v1.2.2 // indirect
	github.com/golang/protobuf v1.5.2 // indirect
	github.com/grpc-ecosystem/grpc-gateway v1.16.0 // indirect
	go.opentelemetry.io/otel/exporters/otlp/internal/retry v1.4.1 // indirect
	go.opentelemetry.io/otel/exporters/otlp/otlptrace v1.4.1 // indirect
	go.opentelemetry.io/otel/trace v1.4.1 // indirect
	go.opentelemetry.io/proto/otlp v0.12.0 // indirect
	golang.org/x/net v0.0.0-20220127200216-cd36cc0744dd // indirect
	google.golang.org/genproto v0.0.0-20220222213610-43724f9ea8cf // indirect
)

require (
	go.opentelemetry.io/contrib/instrumentation/github.com/gorilla/mux/otelmux v0.29.0
	golang.org/x/sys v0.0.0-20220209214540-3681064d5158 // indirect
	golang.org/x/text v0.3.7 // indirect
	google.golang.org/protobuf v1.27.1
)
