package kafka

import (
	"context"
	"fmt"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/propagation"
	semconv "go.opentelemetry.io/otel/semconv/v1.17.0"
	"go.opentelemetry.io/otel/trace"

	"github.com/IBM/sarama"
)

type OTelInterceptor struct {
	tracer     trace.Tracer
	fixedAttrs []attribute.KeyValue
}

// NewOTelInterceptor processes span for intercepted messages and add some
// headers with the span data.
func NewOTelInterceptor() *OTelInterceptor {
	oi := OTelInterceptor{}
	oi.tracer = otel.Tracer("github.com/open-telemetry/opentelemetry-demo/checkoutservice/sarama")

	// These are based on the spec, which was reachable as of 2020-05-15
	// https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/trace/semantic_conventions/messaging.md
	oi.fixedAttrs = []attribute.KeyValue{
		semconv.PeerService("kafka"),
		semconv.MessagingSystem("kafka"),
		semconv.NetTransportTCP,
	}
	return &oi
}

func shouldIgnoreMsg(msg *sarama.ProducerMessage) bool {
	propagationHeaderNames := otel.GetTextMapPropagator().Fields()

	// check message hasn't been here before (retries)
	for _, h := range msg.Headers {
		for _, name := range propagationHeaderNames {
			if string(h.Key) == name {
				return true
			}
		}
	}

	return false
}

func (oi *OTelInterceptor) OnSend(msg *sarama.ProducerMessage) {
	if shouldIgnoreMsg(msg) {
		return
	}

	spanContext, span := oi.tracer.Start(
		context.Background(),
		fmt.Sprintf("%s publish", msg.Topic),
		trace.WithSpanKind(trace.SpanKindProducer),
		trace.WithAttributes(oi.fixedAttrs...),
		trace.WithAttributes(
			semconv.MessagingDestinationKindTopic,
			semconv.MessagingDestinationName(msg.Topic),
			semconv.MessagingOperationPublish,
			semconv.MessagingKafkaDestinationPartition(int(msg.Partition)),
		),
	)
	defer span.End()

	carrier := propagation.MapCarrier{}
	propagator := otel.GetTextMapPropagator()
	propagator.Inject(spanContext, carrier)

	for key, value := range carrier {
		msg.Headers = append(msg.Headers, sarama.RecordHeader{Key: []byte(key), Value: []byte(value)})
	}
}
