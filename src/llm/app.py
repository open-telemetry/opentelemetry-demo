#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from flask import Flask, request, jsonify, Response
import json
import time
import random
import re
import logging

app = Flask(__name__)
logging.getLogger().setLevel(logging.INFO)

def generate_mock_response(messages):
    """Generate a simple mock response based on the conversation"""
    last_message = messages[-1]["content"] if messages else "Hello"

    # Simple mock responses
    responses = [
        f"I understand you said: '{last_message}'. This is a mock LLM response.",
        f"That's an interesting point about '{last_message}'. Let me elaborate...",
        f"Based on your message about '{last_message}', here's my simulated response.",
    ]

    return random.choice(responses)

def parse_product_id(messages):
    last_message = messages[-1]["content"]

    match = re.search(r"product ID:([A-Z0-9]+)", last_message)
    if match:
        return match.group(1).strip()
    raise ValueError("product ID not found in input message")

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    data = request.json
    messages = data.get('messages', [])
    stream = data.get('stream', False)
    model = data.get('model', 'astronomy-llm')
    tools = data.get('tools', None)

    logging.getLogger().info(f"Received a chat completion request: '{messages}'")

    response_text = generate_mock_response(messages)

    if tools is not None:

        product_id = parse_product_id(messages)
        tool_args = f"{{\"product_id\": \"{product_id}\"}}"

        logging.getLogger().info(f"Processing a tool call with args: '{tool_args}'")

        # Non-streaming response
        response = {
            "id": f"chatcmpl-mock-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "requesting a tool call",
                    "tool_calls": [{
                        "id": "call",
                        "type": "function",
                        "function": {
                          "name": "fetch_product_reviews",
                          "arguments": tool_args
                        }
                      }]
                },
                "finish_reason": "tool_calls"
            }],
            "usage": {
                "prompt_tokens": sum(len(m.get("content", "").split()) for m in messages),
                "completion_tokens": len(response_text.split()),
                "total_tokens": sum(len(m.get("content", "").split()) for m in messages) + len(response_text.split())
            }
        }
        return jsonify(response)
    else:
        if stream:
            def generate():
                # Simulate streaming
                words = response_text.split()
                for i, word in enumerate(words):
                    chunk = {
                        "id": f"chatcmpl-mock-{int(time.time())}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": word + " "} if i > 0 else {"role": "assistant", "content": word + " "},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                    time.sleep(0.05)  # Simulate typing delay

                # Final chunk
                final_chunk = {
                    "id": f"chatcmpl-mock-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return Response(generate(), mimetype='text/event-stream')

        else:
            # Non-streaming response
            logging.getLogger().info(f"Processing a response: '{response_text}'")

            response = {
                "id": f"chatcmpl-mock-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": sum(len(m.get("content", "").split()) for m in messages),
                    "completion_tokens": len(response_text.split()),
                    "total_tokens": sum(len(m.get("content", "").split()) for m in messages) + len(response_text.split())
                }
            }
            return jsonify(response)

@app.route('/v1/models', methods=['GET'])
def list_models():
    """List available models"""
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": "astronomy-llm",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "astronomy-shop"
            }
        ]
    })

if __name__ == '__main__':
    print("Mock OpenAI API server starting on http://localhost:8000")
    print("Set your OpenAI base URL to: http://localhost:8000/v1")
    app.run(host='0.0.0.0', port=8000, debug=True)