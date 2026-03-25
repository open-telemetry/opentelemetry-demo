#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


import asyncio
import logging
import os

from dotenv import load_dotenv
from src.agents.agents import Agent
from src.chat_interface.chat_interface import ChatAgentUI, get_chat_ui_config
from src.mcp_server.astronomy_shop_mcp_server import AstronomyShopMcp
from traceloop.sdk import Traceloop

logging.basicConfig(level=logging.INFO)

load_dotenv()

Traceloop.init(
    app_name="AstronomyShopAgent",
    api_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"),
)


async def start_servers():
    """Run both the LangGraph Agent and the MCP server concurrently."""
    tasks = []

    mcp_enabled = os.getenv("MCP_ENABLED", "False") == "True"
    if mcp_enabled:
        mcp = AstronomyShopMcp()
        mcp_server_task = asyncio.to_thread(mcp.run)
        tasks.append(mcp_server_task)
        await asyncio.sleep(2)
        logging.info("MCP Server should be up, launching Agent...")

    agent = Agent()
    tasks.append(agent.launch())

    chat_ui_config = get_chat_ui_config()
    chat_interface = ChatAgentUI(chat_ui_config)
    tasks.append(asyncio.to_thread(chat_interface.launch))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(start_servers())
    except KeyboardInterrupt:
        logging.info("Shutting down servers...")
