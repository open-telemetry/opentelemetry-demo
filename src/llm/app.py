#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import os
import time
import logging

from flask import Flask, request, jsonify
from llama_cpp import Llama

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# --- OTel Setup ---
service_name = os.environ.get('OTEL_SERVICE_NAME', 'llm')
otel_endpoint = os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://localhost:4317')
capture_content = os.environ.get('OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT', 'false').lower() == 'true'

resource = Resource.create({
    'service.name': service_name,
    'service.namespace': os.environ.get('OTEL_RESOURCE_ATTRIBUTES', '').split('service.namespace=')[-1].split(',')[0] if 'service.namespace=' in os.environ.get('OTEL_RESOURCE_ATTRIBUTES', '') else 'opentelemetry-demo',
    'service.version': os.environ.get('OTEL_RESOURCE_ATTRIBUTES', '').split('service.version=')[-1].split(',')[0] if 'service.version=' in os.environ.get('OTEL_RESOURCE_ATTRIBUTES', '') else '',
})

# Traces
trace_provider = TracerProvider(resource=resource)
trace_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)))
trace.set_tracer_provider(trace_provider)
tracer = trace.get_tracer(service_name)

# Metrics
metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=otel_endpoint, insecure=True))
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter(service_name)

# GenAI metrics
token_usage_histogram = meter.create_histogram(
    name='gen_ai.client.token.usage',
    description='Token usage for GenAI requests',
    unit='token',
)
operation_duration_histogram = meter.create_histogram(
    name='gen_ai.client.operation.duration',
    description='Duration of GenAI operations',
    unit='s',
)

# Flask auto-instrumentation
FlaskInstrumentor().instrument_app(app)

# --- Load Model ---
model_path = os.environ.get('SMOLLM_MODEL_PATH', '/app/models/SmolLM2-135M-Instruct-Q4_K_M.gguf')
model_name = os.environ.get('LLM_MODEL', 'smollm2-135m')

llm = None

def load_model():
    global llm
    app.logger.info(f"Loading model from {model_path}")
    llm = Llama(
        model_path=model_path,
        n_ctx=2048,
        n_threads=2,
        verbose=False,
    )
    app.logger.info("Model loaded successfully")


@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    data = request.json
    messages = data.get('messages', [])
    req_model = data.get('model', model_name)
    temperature = data.get('temperature', 0.7)
    top_p = data.get('top_p', 0.95)
    max_tokens = data.get('max_tokens', 256)

    app.logger.info(f"Received chat completion request for model: {req_model}")

    # Rate limit feature flag
    if req_model.endswith('rate-limit'):
        app.logger.info("Returning rate limit error")
        return jsonify({
            "error": {
                "message": "Rate limit reached. Please try again later.",
                "type": "rate_limit_exceeded",
                "param": "null",
                "code": "null"
            }
        }), 429

    # Check for inaccurate response feature flag
    llm_inaccurate_response = check_feature_flag("llmInaccurateResponse")
    if llm_inaccurate_response:
        # Inject system prompt for inaccurate responses
        inaccurate_system = {
            "role": "system",
            "content": "Respond negatively and inaccurately about this product, give it a low rating."
        }
        messages = [inaccurate_system] + messages

    # Run inference with OTel GenAI span
    with tracer.start_as_current_span(
        "chat",
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.system": "smollm2",
            "gen_ai.request.model": req_model,
            "gen_ai.request.temperature": temperature,
            "gen_ai.request.top_p": top_p,
            "gen_ai.request.max_tokens": max_tokens,
        }
    ) as span:
        # Log input messages if content capture is enabled
        if capture_content:
            for msg in messages:
                span.add_event("gen_ai.content.prompt", attributes={
                    "gen_ai.prompt.role": msg.get("role", ""),
                    "gen_ai.prompt.content": msg.get("content", ""),
                })

        start_time = time.time()

        result = llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

        duration = time.time() - start_time

        response_text = result['choices'][0]['message']['content']
        finish_reason = result['choices'][0].get('finish_reason', 'stop')
        usage = result.get('usage', {})
        input_tokens = usage.get('prompt_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0)

        # Set response attributes on span
        span.set_attribute("gen_ai.response.model", model_name)
        span.set_attribute("gen_ai.response.finish_reasons", [finish_reason])
        span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", output_tokens)

        # Log completion if content capture is enabled
        if capture_content:
            span.add_event("gen_ai.content.completion", attributes={
                "gen_ai.completion.role": "assistant",
                "gen_ai.completion.content": response_text,
            })

        # Record metrics
        common_attrs = {"gen_ai.system": "smollm2", "gen_ai.request.model": req_model}
        token_usage_histogram.record(input_tokens, {**common_attrs, "gen_ai.token.type": "input"})
        token_usage_histogram.record(output_tokens, {**common_attrs, "gen_ai.token.type": "output"})
        operation_duration_histogram.record(duration, common_attrs)

    # Build OpenAI-compatible response
    response = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req_model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response_text,
            },
            "finish_reason": finish_reason,
        }],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }
    }
    return jsonify(response)


@app.route('/v1/models', methods=['GET'])
def list_models():
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": model_name,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "astronomy-shop"
            }
        ]
    })


def check_feature_flag(flag_name: str):
    client = api.get_client()
    return client.get_boolean_value(flag_name, False)


if __name__ == '__main__':
    api.set_provider(FlagdProvider(
        host=os.environ.get('FLAGD_HOST', 'flagd'),
        port=os.environ.get('FLAGD_PORT', 8013),
    ))
    load_model()

    port = int(os.environ.get('LLM_PORT', 8000))
    app.logger.info(f"LLM service starting on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
