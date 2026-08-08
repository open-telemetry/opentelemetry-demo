#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import logging
import os

import uvicorn
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from demo_llm.server import create_app

logging.basicConfig(level=logging.INFO)


def configure_telemetry():
    """Wire up the SDK. Endpoint, service name and resource attributes all come
    from the standard OTEL_* environment variables the compose file sets."""
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))


def instrument(app):
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        logging.warning(
            "opentelemetry-instrumentation-fastapi not installed, "
            "serving without HTTP request spans"
        )
        return
    FastAPIInstrumentor.instrument_app(app)


def main():
    configure_telemetry()
    app = create_app()
    instrument(app)
    port = int(os.getenv("DEMO_LLM_PORT", "8012"))
    logging.info("demo-llm serving OpenAI-compatible API on port %s", port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
