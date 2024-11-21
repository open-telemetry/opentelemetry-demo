// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

import (
	"context"
	"math"
	"runtime"

	"go.opentelemetry.io/otel/metric"
)

func recordRuntimeMetrics(meter metric.Meter) error {
	// Create metric instruments

	var (
		err error

		memSys       metric.Int64ObservableUpDownCounter
		pauseTotalMs metric.Int64ObservableCounter
	)

	if pauseTotalMs, err = meter.Int64ObservableCounter(
		"process.runtime.go.gc.pause_total_ms",
		metric.WithDescription("Cumulative nanoseconds in GC stop-the-world pauses since the program started"),
	); err != nil {
		return err
	}

	if memSys, err = meter.Int64ObservableUpDownCounter(
		"process.runtime.go.mem.sys",
		metric.WithUnit("By"),
		metric.WithDescription("Bytes of memory obtained from the OS"),
	); err != nil {
		return err
	}

	// Record the runtime stats periodically
	if _, err := meter.RegisterCallback(
		func(ctx context.Context, o metric.Observer) error {
			var memStats runtime.MemStats
			runtime.ReadMemStats(&memStats)

			o.ObserveInt64(pauseTotalMs, clampUint64(memStats.PauseTotalNs)/1e6) // GC Pause in ms
			o.ObserveInt64(memSys, clampUint64(memStats.Sys))
			return nil
		},
		pauseTotalMs, memSys,
	); err != nil {
		return err
	}

	return nil
}

func clampUint64(v uint64) int64 {
	if v > math.MaxInt64 {
		return math.MaxInt64
	}
	return int64(v)
}
