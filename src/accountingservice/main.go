// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

//go:generate go install google.golang.org/protobuf/cmd/protoc-gen-go
//go:generate go install google.golang.org/grpc/cmd/protoc-gen-go-grpc
//go:generate protoc --go_out=./ --go-grpc_out=./ --proto_path=../../pb ../../pb/demo.proto

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"

	"github.com/IBM/sarama"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	sdkresource "go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"

	"github.com/open-telemetry/opentelemetry-demo/src/accountingservice/kafka"
)

var resource *sdkresource.Resource
var initResourcesOnce sync.Once

func initLogger() *slog.Logger {
	logger := slog.New(slog.NewJSONHandler(os.Stderr, nil)).With("service", "accounting")
	slog.SetDefault(logger)
	return logger
}
func initResource() *sdkresource.Resource {
	initResourcesOnce.Do(func() {
		extraResources, _ := sdkresource.New(
			context.Background(),
			sdkresource.WithOS(),
			sdkresource.WithProcess(),
			sdkresource.WithContainer(),
			sdkresource.WithHost(),
		)
		resource, _ = sdkresource.Merge(
			sdkresource.Default(),
			extraResources,
		)
	})
	return resource
}

func initTracerProvider() (*sdktrace.TracerProvider, error) {
	ctx := context.Background()

	exporter, err := otlptracegrpc.New(ctx)
	if err != nil {
		return nil, err
	}
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(initResource()),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(propagation.TraceContext{}, propagation.Baggage{}))
	return tp, nil
}

func main() {
	logger := initLogger()
	ctx := context.Background()
	tp, err := initTracerProvider()
	if err != nil {
		logger.LogAttrs(ctx, slog.LevelError, "failed to initialize trace provider", slog.String("error", err.Error()))
	}
	defer func() {
		if err := tp.Shutdown(ctx); err != nil {
			logger.LogAttrs(ctx, slog.LevelError, "failed to shotdown properly", slog.String("error", err.Error()))
		}
		logger.LogAttrs(ctx, slog.LevelInfo, "", slog.String("message", "Shotdown trace provider"))
	}()

	var brokers string
	mustMapEnv(&brokers, "KAFKA_SERVICE_ADDR")

	brokerList := strings.Split(brokers, ",")
	logger.LogAttrs(ctx, slog.LevelInfo, "Kafka brokers", slog.String("Kafka brokers", strings.Join(brokerList, ",")))

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM, syscall.SIGKILL)
	defer cancel()
	var consumerGroup sarama.ConsumerGroup
	if consumerGroup, err = kafka.StartConsumerGroup(ctx, brokerList, logger); err != nil {
		logger.LogAttrs(ctx, slog.LevelError, "Failed to start consumer group", slog.String("error", err.Error()))
	}
	defer func() {
		if err := consumerGroup.Close(); err != nil {
			logger.LogAttrs(ctx, slog.LevelError, "Error closing consumer group", slog.String("error", err.Error()))
		}
		logger.Log(ctx, slog.LevelInfo, "Closed consumer group")
	}()

	<-ctx.Done()

	logger.Log(ctx, slog.LevelInfo, "message", "Accounting service exited")
}

func mustMapEnv(target *string, envKey string) {
	v := os.Getenv(envKey)
	if v == "" {
		panic(fmt.Sprintf("environment variable %q not set", envKey))
	}
	*target = v
}
