// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package xk6otel bridges the OTel Go SDK into k6's JavaScript runtime so
// that load test scripts can create spans, propagate trace context to the
// system under test via W3C traceparent headers, and emit correlated log
// records. Register with xk6 as "k6/x/otel".
package xk6otel

import (
	"context"
	"fmt"
	"os"
	"sync"
	"time"

	"github.com/grafana/sobek"
	"go.k6.io/k6/v2/js/modules"
	"go.opentelemetry.io/contrib/instrumentation/runtime"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploghttp"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetrichttp"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	otellog "go.opentelemetry.io/otel/log"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
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

		extraResources, _ := resource.New(ctx,
			resource.WithOS(),
			resource.WithProcess(),
			resource.WithContainer(),
			resource.WithHost(),
		)
		res, err := resource.Merge(resource.Default(), extraResources)
		if err != nil {
			res = resource.Default()
		}

		traceExp, err := otlptracehttp.New(ctx)
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
		if logExp, lerr := otlploghttp.New(ctx); lerr != nil {
			fmt.Fprintf(os.Stderr, "xk6-otel: warning: OTLP log exporter unavailable: %v\n", lerr)
		} else {
			lp := sdklog.NewLoggerProvider(
				sdklog.WithProcessor(sdklog.NewBatchProcessor(logExp)),
				sdklog.WithResource(res),
			)
			globalLogger = lp.Logger("load-generator")
		}

		// Metric provider — non-fatal if unavailable so traces still work.
		if metricExp, merr := otlpmetrichttp.New(ctx); merr != nil {
			fmt.Fprintf(os.Stderr, "xk6-otel: warning: OTLP metric exporter unavailable: %v\n", merr)
		} else {
			mp := sdkmetric.NewMeterProvider(
				sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExp)),
				sdkmetric.WithResource(res),
			)
			if err := runtime.Start(
				runtime.WithMeterProvider(mp),
				runtime.WithMinimumReadMemStatsInterval(time.Second),
			); err != nil {
				fmt.Fprintf(os.Stderr, "xk6-otel: warning: runtime instrumentation unavailable: %v\n", err)
			}
		}
	})
}

// ---- k6 module wiring -------------------------------------------------------

// RootModule is the module factory; one instance exists for the whole test run.
type RootModule struct{}

// ModuleInstance is created once per VU that imports the module. ctxStack
// tracks the currently "active" span context, mirroring the Locust
// implementation's use of context.get_current() so that nested startSpan()
// calls (e.g. user_add_to_cart inside checkout()) become child spans instead
// of unrelated root traces.
type ModuleInstance struct {
	vu       modules.VU
	ctxStack []context.Context
	lastIter int64
}

var (
	_ modules.Module   = &RootModule{}
	_ modules.Instance = &ModuleInstance{}
)

// New returns the RootModule that k6 calls to create per-VU instances.
func New() *RootModule { return &RootModule{} }

func (*RootModule) NewModuleInstance(vu modules.VU) modules.Instance {
	return &ModuleInstance{vu: vu}
}

// currentContext returns the context of the innermost open span, or
// context.Background() if there is none. The stack is reset at the start of
// each iteration so a span left unclosed by a failed iteration (e.g. a
// thrown exception) can't leak into the next one.
func (m *ModuleInstance) currentContext() context.Context {
	if state := m.vu.State(); state != nil && state.Iteration != m.lastIter {
		m.lastIter = state.Iteration
		m.ctxStack = nil
	}
	if len(m.ctxStack) == 0 {
		return context.Background()
	}
	return m.ctxStack[len(m.ctxStack)-1]
}

func (m *ModuleInstance) pushContext(ctx context.Context) {
	m.ctxStack = append(m.ctxStack, ctx)
}

func (m *ModuleInstance) popContext() {
	if len(m.ctxStack) > 0 {
		m.ctxStack = m.ctxStack[:len(m.ctxStack)-1]
	}
}

// Exports surfaces the named exports { Tracer } to JavaScript.
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

	if err := call.This.Set("startSpan", makeStartSpan(m, rt)); err != nil {
		panic(rt.NewGoError(err))
	}

	return nil
}

// makeStartSpan returns the JS function that scripts call as tracer.startSpan().
//
// Signature: startSpan(name, attrs?)
//
// Starts the span as a child of whichever span is currently open on this VU
// (see ModuleInstance.currentContext), so e.g. the user_add_to_cart span
// started inside checkout() nests under user_checkout_single rather than
// becoming its own root trace.
//
// Returns an object with:
//   - traceParent() → W3C traceparent string for injection into HTTP request headers
//   - log(message)  → emits a correlated OTel log record
//   - end()         → ends the span
func makeStartSpan(m *ModuleInstance, rt *sobek.Runtime) func(sobek.FunctionCall) sobek.Value {
	return func(fc sobek.FunctionCall) sobek.Value {
		name := fc.Argument(0).String()

		var kvs []attribute.KeyValue
		if len(fc.Arguments) > 1 && !sobek.IsUndefined(fc.Argument(1)) {
			kvs = jsObjToAttrs(fc.Argument(1).ToObject(rt))
		}

		ctx, span := globalTracer.Start(
			m.currentContext(),
			name,
			trace.WithAttributes(kvs...),
			trace.WithSpanKind(trace.SpanKindClient),
		)
		m.pushContext(ctx)

		obj := rt.NewObject()
		if err := obj.Set("traceParent", makeTraceParent(span)); err != nil {
			panic(rt.NewGoError(err))
		}
		if err := obj.Set("end", func() {
			span.End()
			m.popContext()
		}); err != nil {
			panic(rt.NewGoError(err))
		}
		if err := obj.Set("log", makeSpanLog(span)); err != nil {
			panic(rt.NewGoError(err))
		}
		return rt.ToValue(obj)
	}
}

// makeTraceParent returns the W3C traceparent for the given span as a JS callable.
// Scripts use this to inject trace context into outgoing HTTP request headers so
// backend services can correlate their spans with the load generator span.
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
