#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


import asyncio
import logging

from dotenv import load_dotenv
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from src.chat_interface.chat_interface import ChatAgentUI, get_chat_ui_config
from src.opamp import start_opamp_agent, stop_opamp_agent

logging.basicConfig(level=logging.INFO)

load_dotenv()


def _configure_telemetry() -> None:
    meter_provider = MeterProvider(
        metric_readers=[
            PeriodicExportingMetricReader(OTLPMetricExporter()),
        ],
    )
    metrics.set_meter_provider(meter_provider)

    tracer_provider = TracerProvider(meter_provider=meter_provider)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    RequestsInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()


_configure_telemetry()


async def start_servers():
    """Runs chatbot server"""
    opamp_agent = start_opamp_agent()
    tasks = []

    chat_ui_config = get_chat_ui_config()
    chat_interface = ChatAgentUI(chat_ui_config)
    tasks.append(asyncio.to_thread(chat_interface.launch))

    try:
        await asyncio.gather(*tasks)
    finally:
        stop_opamp_agent(opamp_agent)


if __name__ == "__main__":
    try:
        asyncio.run(start_servers())
    except KeyboardInterrupt:
        logging.info("Shutting down servers...")
