#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


import asyncio
import logging
import os

from dotenv import load_dotenv
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from src.mcp_server.astronomy_shop_mcp_server import AstronomyShopMcp
from traceloop.sdk import Traceloop

logging.basicConfig(level=logging.INFO)

load_dotenv()

Traceloop.init(
    app_name=os.getenv("OTEL_SERVICE_NAME", "mcp"),
    api_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"),
)

HTTPXClientInstrumentor().instrument()


async def start_servers():
    """Runs the MCP server."""
    tasks = []
    mcp = AstronomyShopMcp()
    mcp_server_task = asyncio.to_thread(mcp.run)
    tasks.append(mcp_server_task)
    logging.info("Starting MCP server on port %s", mcp.port)

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(start_servers())
    except KeyboardInterrupt:
        logging.info("Shutting down servers...")
