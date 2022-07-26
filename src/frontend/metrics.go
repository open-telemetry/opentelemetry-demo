package main

import (
	"context"
	"io"
	"net/http"

	"go.opentelemetry.io/otel/metric"
	"go.opentelemetry.io/otel/metric/instrument/syncfloat64"
	"go.opentelemetry.io/otel/metric/instrument/syncint64"
)

var (
	meter                    metric.Meter
	httpRequestCounter       syncint64.Counter
	httpServerLatency        syncfloat64.Histogram
	httpServerRequestSize    syncint64.Histogram
	httpServerResponseSize   syncint64.Histogram
	httpServerActiveRequests syncint64.Counter
)

var _ io.ReadCloser = &instrumentedBody{}

type instrumentedBody struct {
	io.ReadCloser
	read int64
	err  error
}

func (w *instrumentedBody) Read(b []byte) (int, error) {
	n, err := w.ReadCloser.Read(b)
	w.read += int64(n)
	w.err = err
	return n, err
}

func (w *instrumentedBody) Close() error {
	return w.ReadCloser.Close()
}

var _ http.ResponseWriter = &instrumentedResponseWriter{}

type instrumentedResponseWriter struct {
	http.ResponseWriter
	ctx         context.Context // used to inject the header
	written     int64
	statusCode  int
	err         error
	wroteHeader bool
}

func (w *instrumentedResponseWriter) Header() http.Header {
	return w.ResponseWriter.Header()
}

func (w *instrumentedResponseWriter) Write(p []byte) (int, error) {
	if !w.wroteHeader {
		w.WriteHeader(http.StatusOK)
	}
	n, err := w.ResponseWriter.Write(p)
	n1 := int64(n)
	w.written += n1
	w.err = err
	return n, err
}

func (w *instrumentedResponseWriter) WriteHeader(statusCode int) {
	if w.wroteHeader {
		return
	}
	w.wroteHeader = true
	w.statusCode = statusCode
	w.ResponseWriter.WriteHeader(statusCode)
}
