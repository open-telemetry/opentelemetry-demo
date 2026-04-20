#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


import asyncio
import logging

from dotenv import load_dotenv
from src.chat_interface.chat_interface import ChatAgentUI, get_chat_ui_config

logging.basicConfig(level=logging.INFO)

load_dotenv()


async def start_servers():
    """Runs chatbot server"""
    tasks = []

    chat_ui_config = get_chat_ui_config()
    chat_interface = ChatAgentUI(chat_ui_config)
    tasks.append(asyncio.to_thread(chat_interface.launch))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(start_servers())
    except KeyboardInterrupt:
        logging.info("Shutting down servers...")
