#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from flask import Flask, request, jsonify, Response
import json
import time
import random
import re
import os
import logging

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

product_review_summaries = None
product_review_summaries_file_path = "./product-review-summaries.json"

inaccurate_product_review_summaries = None
inaccurate_product_review_summaries_file_path = "./inaccurate-product-review-summaries.json"

def load_product_review_summaries(file_path):
    try:
        with open(file_path, 'r') as file:

            """
            Converts a JSON string into an internal dictionary optimized for quick lookups.
            The keys of the internal dictionary will be product_ids.
            """
            try:
                data = json.load(file)
                summaries = data.get("product-review-summaries", [])

                # Create a dictionary where product_id is the key
                # and the value is a dictionary of its details (score, summary)
                product_review_summaries = {}
                for product in summaries:
                    product_id = product.get("product_id")
                    if product_id: # Ensure product_id exists before adding
                        product_review_summaries[product_id] = {
                            "average_score": product.get("average_score"),
                            "product_review_summary": product.get("product_review_summary")
                        }
                return product_review_summaries
            except json.JSONDecodeError:
                print("Error: Invalid JSON string provided during initialization.")
                return {}

    except FileNotFoundError:
        app.logger.error(f"Error: The file '{product_review_summaries_file_path}' was not found.")
    except json.JSONDecodeError:
        app.logger.error(f"Error: Failed to decode JSON from the file '{product_review_summaries_file_path}'. Check for malformed JSON.")
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")


def generate_response(product_id):

    """Generate a response by providing the pre-generated summary for the specified product"""
    product_review_summary = None

    llm_inaccurate_response = check_feature_flag("llmInaccurateResponse")
    app.logger.info(f"llmInaccurateResponse feature flag: {llm_inaccurate_response}")
    if llm_inaccurate_response and product_id == "L9ECAV7KIM":
        app.logger.info(f"Returning an inaccurate response for product_id: {product_id}")
        product_review_summary = inaccurate_product_review_summaries.get(product_id)
    else:
        product_review_summary = product_review_summaries.get(product_id)

    # Convert the dictionary to a JSON string
    json_string = json.dumps(product_review_summary)

    return json_string

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

    app.logger.info(f"Received a chat completion request: '{messages}'")

    product_id = parse_product_id(messages)

    if tools is not None:

        tool_args = f"{{\"product_id\": \"{product_id}\"}}"

        app.logger.info(f"Processing a tool call with args: '{tool_args}'")

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
                "completion_tokens": "0",
                "total_tokens": sum(len(m.get("content", "").split()) for m in messages)
            }
        }
        return jsonify(response)

    else:
        llm_rate_limit_error = check_feature_flag("llmRateLimitError")
        app.logger.info(f"llmRateLimitError feature flag: {llm_rate_limit_error}")
        if llm_rate_limit_error:
            random_number = random.random()
            app.logger.info(f"Generated a random number: {str(random_number)}")
            # return a rate limit error 20% of the time
            if random_number < 0.5:
                response = {
                    "error": {
                        "message": "Rate limit reached. Please try again later.",
                        "type": "rate_limit_exceeded",
                        "param": "null",
                        "code": "null"
                    }
                }
                return jsonify(response), 429

        # Otherwise, return a normal response
        response_text = generate_response(product_id)

        app.logger.info(f"Processing a response: '{response_text}'")

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

def check_feature_flag(flag_name: str):
    # Initialize OpenFeature
    client = api.get_client()
    return client.get_boolean_value(flag_name, False)

if __name__ == '__main__':

    api.set_provider(FlagdProvider(host=os.environ.get('FLAGD_HOST', 'flagd'), port=os.environ.get('FLAGD_PORT', 8013)))
    product_review_summaries = load_product_review_summaries(product_review_summaries_file_path)
    inaccurate_product_review_summaries = load_product_review_summaries(inaccurate_product_review_summaries_file_path)

    app.logger.info(product_review_summaries)

    print("OpenAI API server starting on http://localhost:8000")
    print("Set your OpenAI base URL to: http://localhost:8000/v1")
    app.run(host='0.0.0.0', port=8000, debug=True)
