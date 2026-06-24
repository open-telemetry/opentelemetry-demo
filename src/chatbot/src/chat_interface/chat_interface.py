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

    def chat_with_agent(self, message, history, request: gr.Request):
        try:
            # session_id = request.session_hash or self.config.sessionId
            payload = {
                # "session_id": session_id,
                "message": message,
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
                "Show all available products in the store.",
                "What currencies are supported by the Astronomy Shop?",
                "What current promotions are available on binoculars?",
            ],
        }

        if agent_config:
            config.update(
                agent_config[0] if isinstance(agent_config, list) else agent_config
            )

        examples = [
            ex[0] if isinstance(ex, (list, tuple)) else ex
            for ex in config["examples"]
        ]

        def respond(message, history, request: gr.Request):
            message = (message or "").strip()
            if not message:
                return "", history
            history = list(history or [])
            reply = self.chat_with_agent(message, history, request)
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": reply})
            return "", history

        def respond_fresh(message, request: gr.Request):
            # Sample-question clicks start a brand new conversation with
            # empty history, rather than continuing the current chat.
            message = (message or "").strip()
            if not message:
                return "", []
            reply = self.chat_with_agent(message, [], request)
            return "", [
                {"role": "user", "content": message},
                {"role": "assistant", "content": reply},
            ]

        with gr.Blocks(
            title=config["title"], analytics_enabled=False
        ) as chatbot_ui:
            gr.Markdown(f"# {config['title']}")
            gr.Markdown(config["description"])

            chatbot = gr.Chatbot(height="70vh")
            textbox = gr.Textbox(
                placeholder="Type a message...",
                show_label=False,
                autofocus=True,
            )

            gr.Markdown("Sample questions:")
            with gr.Row():
                example_buttons = [gr.Button(ex, size="sm") for ex in examples]

            textbox.submit(
                respond, [textbox, chatbot], [textbox, chatbot]
            )

            for button, example in zip(example_buttons, examples):
                button.click(
                    respond_fresh,
                    [gr.State(example)],
                    [textbox, chatbot],
                )

        chatbot_ui.launch(
            server_name=self.config.uiBaseUrl,
            server_port=self.config.uiPort,
            root_path=self.config.rootPath,
        )


def get_chat_ui_config():
    chat_ui_config = ChatUiConfig(
        uiBaseUrl=os.getenv("CHATBOT_ENDPOINT", "::"),
        uiPort=int(os.getenv("CHATBOT_PORT", "7860")),
        sessionId=str(uuid.uuid4()),
        timeout=int(os.getenv("AGENT_CHAT_INTERFACE_TIMEOUT", "300")),
        agentBaseUrl=f"http://{os.getenv('AGENT_ENDPOINT', '0.0.0.0')}:{os.getenv('AGENT_PORT', '8010')}/prompt",
        rootPath=os.getenv("CHATBOT_ROOT_PATH", ""),
    )
    return chat_ui_config
