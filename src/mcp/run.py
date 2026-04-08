#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


import asyncio
import logging
import os

from dotenv import load_dotenv
from src.mcp_server.astronomy_shop_mcp_server import AstronomyShopMcp
from traceloop.sdk import Traceloop

logging.basicConfig(level=logging.INFO)

load_dotenv()

Traceloop.init(
    app_name="AstronomyShopAgentMCP",
    api_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"),
)


async def start_servers():
    """Run both the LangGraph Agent and the MCP server concurrently."""
    tasks = []
    mcp = AstronomyShopMcp()
    mcp_server_task = asyncio.to_thread(mcp.run)
    tasks.append(mcp_server_task)
    logging.info("MCP Server should be up, launching Agent...")

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(start_servers())
    except KeyboardInterrupt:
        logging.info("Shutting down servers...")
