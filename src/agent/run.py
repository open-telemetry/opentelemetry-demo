#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


import asyncio
import logging
import os

from dotenv import load_dotenv
from src.agents.agents import Agent
from traceloop.sdk import Traceloop

logging.basicConfig(level=logging.INFO)

load_dotenv()

Traceloop.init(
    app_name="AstronomyShopAgent",
    api_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"),
)


async def start_servers():
    """Run the LangGraph Agent server"""
    tasks = []
    agent = Agent()
    tasks.append(agent.launch())
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(start_servers())
    except KeyboardInterrupt:
        logging.info("Shutting down servers...")
