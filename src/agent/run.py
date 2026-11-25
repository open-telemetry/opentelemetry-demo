#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


import asyncio
import logging
import os

from dotenv import load_dotenv
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from src.agents.feature_flags import init_feature_flags
from traceloop.sdk import Traceloop

logging.basicConfig(level=logging.INFO)

load_dotenv()

Traceloop.init(
    app_name=os.getenv("OTEL_SERVICE_NAME", "agent"),
)

init_feature_flags()

HTTPXClientInstrumentor().instrument()

# Import after instrumenting httpx: vcrpy (imported through src.agents.agents)
# keeps the httpx transport methods it finds at import time, see
# https://github.com/open-telemetry/opentelemetry-demo/issues/4388
from src.agents.agents import Agent

if not OpenAIInstrumentor().is_instrumented_by_opentelemetry:
    OpenAIInstrumentor().instrument()


async def start_servers():
    """Run the LangGraph Agent server"""
    tasks = []
    agent = Agent()
    FastAPIInstrumentor.instrument_app(agent.app)
    tasks.append(agent.launch())
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(start_servers())
    except KeyboardInterrupt:
        logging.info("Shutting down servers...")
