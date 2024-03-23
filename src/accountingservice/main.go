// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

//go:generate go install google.golang.org/protobuf/cmd/protoc-gen-go
//go:generate go install google.golang.org/grpc/cmd/protoc-gen-go-grpc
//go:generate protoc --go_out=./ --go-grpc_out=./ --proto_path=../../pb ../../pb/demo.proto

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"

	"github.com/IBM/sarama"
	"github.com/sirupsen/logrus"
	"github.com/uptrace/opentelemetry-go-extra/otellogrus"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	sdkresource "go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"

	"github.com/open-telemetry/opentelemetry-demo/src/accountingservice/kafka"
)

var log *logrus.Logger
var resource *sdkresource.Resource
var initResourcesOnce sync.Once

func init() {
	log = logrus.New()
	log.AddHook(otellogrus.NewHook(otellogrus.WithLevels(
		logrus.PanicLevel,
		logrus.FatalLevel,
		logrus.ErrorLevel,
		logrus.WarnLevel,
	)))
	log.Out = os.Stdout
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
	ctx := context.Background()
	tp, err := initTracerProvider()
	if err != nil {
		log.WithContext(ctx).WithContext(ctx)
	}
	defer func() {
		if err := tp.Shutdown(ctx); err != nil {
			log.WithContext(ctx).WithError(err)
		}
		log.WithContext(ctx).WithField("Message", "Shotdown trace provider")
	}()

	var brokers string
	mustMapEnv(&brokers, "KAFKA_SERVICE_ADDR")

	brokerList := strings.Split(brokers, ",")
	log.WithField("Kafka brokers: %s", strings.Join(brokerList, ", "))

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM, syscall.SIGKILL)
	defer cancel()
	var consumerGroup sarama.ConsumerGroup
	if consumerGroup, err = kafka.StartConsumerGroup(ctx, brokerList, log); err != nil {
		log.WithContext(ctx).WithError(err)
	}
	defer func() {
		if err := consumerGroup.Close(); err != nil {
			log.WithContext(ctx).WithField("Error closing consumer group: %v", err)
		}
		log.WithContext(ctx).WithField("Message", "Closed consumer group")
	}()

	<-ctx.Done()

	log.WithContext(ctx).WithField("Message", "Accounting service exited")
}

func mustMapEnv(target *string, envKey string) {
	v := os.Getenv(envKey)
	if v == "" {
		panic(fmt.Sprintf("environment variable %q not set", envKey))
	}
	*target = v
}
