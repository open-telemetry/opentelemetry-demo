#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import uuid

import gradio as gr
import requests
from pydantic import BaseModel


class ChatUiConfig(BaseModel):
    uiBaseUrl: str
    uiPort: int
    sessionId: str
    timeout: int
    agentBaseUrl: str
    rootPath: str = ""


class ChatAgentUI:
    def __init__(self, chat_ui_config: ChatUiConfig):
        self.config = chat_ui_config

    def chat_with_agent(self, message, history):
        try:
            payload = {
                "message": message,
                "session_id": self.config.sessionId,
                "history": history,
            }
            logging.info(f"Sending request {payload} to Agent")
            response = requests.post(
                self.config.agentBaseUrl, json=payload, timeout=self.config.timeout
            )
            response.raise_for_status()

            agent_data = response.json().get("response", {})
            messages = agent_data.get("messages", [])
            if messages and isinstance(messages, list):
                return messages[-1].get(
                    "content", "Agent returned an empty message body."
                )
            return "Error: Received an unexpected response format from the agent."

        except Exception as e:
            logging.error(f"Error : {e}")
            return f"Error: {e}"

    def launch(self, agent_config=None):
        config = {
            "title": "Astronomy Shop agent",
            "description": "Ask me about the astronomy shop application, I will ask for more information if needed.",
            "examples": [
                [
                    "What are the categories of products available in Astronomy Shop Application and what are the products in each category"
                ],
                ["Get me all shipping codes in Astronomy Shop Application?"],
                ["Get all the items in the cart for user anonymous-1"],
            ],
        }

        if agent_config:
            config.update(
                agent_config[0] if isinstance(agent_config, list) else agent_config
            )

        chatbot_ui = gr.ChatInterface(
            fn=self.chat_with_agent,
            title=config["title"],
            description=config["description"],
            examples=config["examples"],
            chatbot=gr.Chatbot(height="70vh"),
        )

        chatbot_ui.launch(
            server_name=self.config.uiBaseUrl,
            server_port=self.config.uiPort,
            root_path=self.config.rootPath,
        )


def get_chat_ui_config():
    chat_ui_config = ChatUiConfig(
        uiBaseUrl=os.getenv("CHATBOT_ENDPOINT", "0.0.0.0"),
        uiPort=int(os.getenv("CHATBOT_PORT", "7860")),
        sessionId=str(uuid.uuid4()),
        timeout=int(os.getenv("AGENT_CHAT_INTERFACE_TIMEOUT", "300")),
        agentBaseUrl=f"http://{os.getenv('AGENT_ENDPOINT', '0.0.0.0')}:{os.getenv('AGENT_PORT', '8010')}/prompt",
        rootPath=os.getenv("CHATBOT_ROOT_PATH", ""),
    )
    return chat_ui_config
