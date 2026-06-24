// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package xk6otel provides a k6 extension that lets load test scripts create
// OpenTelemetry root spans, child spans, emit log records, and propagate trace
// context to the system under test via W3C traceparent headers.
// Register with xk6 as "k6/x/otel".
package xk6otel

import (
	"context"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/grafana/sobek"
	"go.k6.io/k6/v2/js/modules"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	otellog "go.opentelemetry.io/otel/log"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"
)

func init() {
	modules.Register("k6/x/otel", New())
}

// ---- global providers (shared across all VUs) --------------------------------

var (
	globalTracer trace.Tracer
	globalLogger otellog.Logger
	providerOnce sync.Once
	providerErr  error
)

func initProviders() {
	providerOnce.Do(func() {
		ctx := context.Background()

		endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
		if endpoint == "" {
			endpoint = "localhost:4317"
		}
		endpoint = strings.TrimPrefix(endpoint, "https://")
		endpoint = strings.TrimPrefix(endpoint, "http://")

		serviceName := os.Getenv("OTEL_SERVICE_NAME")
		if serviceName == "" {
			serviceName = "load-generator"
		}

		res, err := resource.New(ctx,
			resource.WithFromEnv(),
			resource.WithAttributes(semconv.ServiceName(serviceName)),
		)
		if err != nil {
			res = resource.Default()
		}

		// Trace provider
		traceExp, err := otlptracegrpc.New(ctx,
			otlptracegrpc.WithEndpoint(endpoint),
			otlptracegrpc.WithInsecure(),
		)
		if err != nil {
			providerErr = fmt.Errorf("xk6-otel: creating OTLP trace exporter: %w", err)
			return
		}
		tp := sdktrace.NewTracerProvider(
			sdktrace.WithBatcher(traceExp),
			sdktrace.WithResource(res),
			sdktrace.WithSampler(sdktrace.AlwaysSample()),
		)
		globalTracer = tp.Tracer("load-generator")

		// Log provider — non-fatal if unavailable so traces still work.
		logExp, lerr := otlploggrpc.New(ctx,
			otlploggrpc.WithEndpoint(endpoint),
			otlploggrpc.WithInsecure(),
		)
		if lerr != nil {
			fmt.Fprintf(os.Stderr, "xk6-otel: warning: OTLP log exporter unavailable: %v\n", lerr)
			return
		}
		lp := sdklog.NewLoggerProvider(
			sdklog.WithProcessor(sdklog.NewBatchProcessor(logExp)),
			sdklog.WithResource(res),
		)
		globalLogger = lp.Logger("load-generator")
	})
}

// parseTraceparent parses a W3C traceparent string ("00-<traceID>-<spanID>-<flags>")
// into an OTel SpanContext suitable for use as a parent context.
func parseTraceparent(tp string) (trace.SpanContext, error) {
	parts := strings.Split(tp, "-")
	if len(parts) != 4 || parts[0] != "00" {
		return trace.SpanContext{}, fmt.Errorf("invalid traceparent: %q", tp)
	}
	traceID, err := trace.TraceIDFromHex(parts[1])
	if err != nil {
		return trace.SpanContext{}, fmt.Errorf("invalid trace ID in traceparent: %w", err)
	}
	spanID, err := trace.SpanIDFromHex(parts[2])
	if err != nil {
		return trace.SpanContext{}, fmt.Errorf("invalid span ID in traceparent: %w", err)
	}
	return trace.NewSpanContext(trace.SpanContextConfig{
		TraceID:    traceID,
		SpanID:     spanID,
		TraceFlags: trace.FlagsSampled,
		Remote:     true,
	}), nil
}

// ---- k6 module wiring -------------------------------------------------------

// RootModule is the module factory; one instance exists for the whole test run.
type RootModule struct{}

// ModuleInstance is created once per VU that imports the module.
type ModuleInstance struct{ vu modules.VU }

var (
	_ modules.Module   = &RootModule{}
	_ modules.Instance = &ModuleInstance{}
)

// New returns the RootModule that k6 calls to create per-VU instances.
func New() *RootModule { return &RootModule{} }

func (*RootModule) NewModuleInstance(vu modules.VU) modules.Instance {
	return &ModuleInstance{vu: vu}
}

// Exports surfaces the named export { Tracer } to JavaScript.
func (m *ModuleInstance) Exports() modules.Exports {
	return modules.Exports{
		Named: map[string]any{
			"Tracer": m.newTracer,
		},
	}
}

// newTracer is called when the script does `new Tracer()`. Sobek recognises
// the ConstructorCall signature and treats the function as a JS constructor.
func (m *ModuleInstance) newTracer(call sobek.ConstructorCall, rt *sobek.Runtime) *sobek.Object {
	initProviders()
	if providerErr != nil {
		panic(rt.NewGoError(providerErr))
	}

	if err := call.This.Set("startSpan", makeStartSpan(rt)); err != nil {
		panic(rt.NewGoError(err))
	}

	return nil
}

// makeStartSpan returns the JS function that scripts call as tracer.startSpan().
//
// Signature: startSpan(name, attrs?, parentTraceparent?)
//
// The optional third argument is a W3C traceparent string. When provided the
// new span is created as a child of that parent; otherwise it is a root span.
func makeStartSpan(rt *sobek.Runtime) func(sobek.FunctionCall) sobek.Value {
	return func(fc sobek.FunctionCall) sobek.Value {
		name := fc.Argument(0).String()

		var kvs []attribute.KeyValue
		if len(fc.Arguments) > 1 && !sobek.IsUndefined(fc.Argument(1)) {
			kvs = jsObjToAttrs(fc.Argument(1).ToObject(rt))
		}

		ctx := context.Background()
		if len(fc.Arguments) > 2 {
			if tp := fc.Argument(2).String(); tp != "" && tp != "undefined" {
				if sc, err := parseTraceparent(tp); err == nil {
					ctx = trace.ContextWithSpanContext(ctx, sc)
				}
			}
		}

		_, span := globalTracer.Start(
			ctx,
			name,
			trace.WithAttributes(kvs...),
			trace.WithSpanKind(trace.SpanKindClient),
		)

		obj := rt.NewObject()
		if err := obj.Set("traceParent", makeTraceParent(span)); err != nil {
			panic(rt.NewGoError(err))
		}
		if err := obj.Set("end", span.End); err != nil {
			panic(rt.NewGoError(err))
		}
		if err := obj.Set("log", makeSpanLog(span)); err != nil {
			panic(rt.NewGoError(err))
		}
		return rt.ToValue(obj)
	}
}

// makeTraceParent returns the W3C traceparent for the given span as a JS callable.
func makeTraceParent(span trace.Span) func() string {
	return func() string {
		sc := span.SpanContext()
		return fmt.Sprintf("00-%s-%s-01", sc.TraceID(), sc.SpanID())
	}
}

// makeSpanLog returns the JS function exposed as span.log(message).
// Emits an OTel log record correlated with the span's trace and span IDs.
func makeSpanLog(span trace.Span) func(sobek.FunctionCall) sobek.Value {
	return func(fc sobek.FunctionCall) sobek.Value {
		if globalLogger == nil {
			return nil
		}
		msg := fc.Argument(0).String()
		sc := span.SpanContext()

		var r otellog.Record
		r.SetTimestamp(time.Now())
		r.SetSeverity(otellog.SeverityInfo)
		r.SetBody(otellog.StringValue(msg))

		// Inject span context so the SDK attaches trace/span IDs to the record.
		ctx := trace.ContextWithSpanContext(context.Background(), sc)
		globalLogger.Emit(ctx, r)
		return nil
	}
}

// ---- attribute conversion ---------------------------------------------------

func jsObjToAttrs(obj *sobek.Object) []attribute.KeyValue {
	keys := obj.Keys()
	kvs := make([]attribute.KeyValue, 0, len(keys))
	for _, k := range keys {
		switch v := obj.Get(k).Export().(type) {
		case string:
			kvs = append(kvs, attribute.String(k, v))
		case float64:
			kvs = append(kvs, attribute.Float64(k, v))
		case int64:
			kvs = append(kvs, attribute.Int64(k, v))
		case bool:
			kvs = append(kvs, attribute.Bool(k, v))
		default:
			kvs = append(kvs, attribute.String(k, fmt.Sprintf("%v", v)))
		}
	}
	return kvs
}
