#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, List

import uvicorn
from fastapi import FastAPI, HTTPException
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_mcp_adapters.tools import load_mcp_tools
from pydantic import BaseModel
from src.agents.llm import ChatLLM
from src.agents.mcp_client import MCPClient
from src.agents.tools import (
    add_to_cart,
    checkout,
    empty_cart,
    get_ads,
    get_cart,
    get_product,
    get_recommendations,
    get_shipping_quote,
    get_supported_currencies,
    list_products,
)
from traceloop.sdk.decorators import workflow


class ChatRequest(BaseModel):
    message: str
    history: List[Dict] = []


class Agent:
    def __init__(self):
        self.app = FastAPI(lifespan=self.lifespan)
        self.app.post("/prompt")(self.handle_prompt)
        self.agentRecursionLimit = int(os.getenv("GRAPH_RECURSION_LIMIT", "25"))
        self.mcp_server_url = f"http://{os.getenv('MCP_ENDPOINT', '0.0.0.0')}:{os.getenv('MCP_PORT', '8011')}/mcp"

        self.mcp_server = None

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        mcp_enabled = os.getenv("MCP_ENABLED", "False") == "True"
        if mcp_enabled:
            logging.info("MCP tools enabled")
            self.mcp_server = MCPClient()
            await self.mcp_server.connect_to_mcp_server(self.mcp_server_url)
        yield
        if self.mcp_server:
            await self.mcp_server.cleanup()

    async def handle_prompt(self, request: ChatRequest):
        return await self.run_agent(request.message)

    async def get_tool_list(self):
        mcp_enabled = os.getenv("MCP_ENABLED", "False") == "True"
        if mcp_enabled and self.mcp_server is not None:
            return await load_mcp_tools(self.mcp_server.session)
        else:
            tool_list = [
                add_to_cart,
                checkout,
                convert_currency,
                empty_cart,
                get_ads,
                get_cart,
                get_product,
                get_recommendations,
                get_shipping_quote,
                get_supported_currencies,
                list_products,
            ]
            return [tool(t) for t in tool_list]

    @workflow(name="astronomy_shop_agent_workflow")
    async def run_agent(self, input_prompt):
        model = ChatLLM()
        tools = await self.get_tool_list()
        agent = create_agent(
            model,
            tools=tools,
            system_prompt="You are a helpful assistant. Be concise and accurate.",
        )
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": input_prompt}]}
            )
            return {"response": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def launch(self):
        agent_port = int(os.getenv("AGENT_PORT", "8010"))
        agent_config = uvicorn.Config(
            app=self.app,
            host="0.0.0.0",
            port=agent_port,
            log_level="info",
        )
        agent_server = uvicorn.Server(agent_config)
        await agent_server.serve()
