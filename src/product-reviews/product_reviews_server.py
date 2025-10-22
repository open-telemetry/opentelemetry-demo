#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


# Python
import os
import json
from concurrent import futures

# Pip
import grpc
from opentelemetry import trace, metrics
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter,
)
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

# Local
import logging
import demo_pb2
import demo_pb2_grpc
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc
from database import fetch_product_reviews, fetch_product_reviews_from_db

from metrics import (
    init_metrics
)

# OpenAI
from openai import OpenAI

llm_base_url = None
llm_api_key = None
llm_model = None

# --- Define the tool for the OpenAI API ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "fetch_product_reviews",
            "description": "Executes a SQL query to retrieve reviews for a particular product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The product ID to fetch product reviews for.",
                    }
                },
                "required": ["product_id"],
            },
        }
    }
]

class ProductReviewService(demo_pb2_grpc.ProductReviewServiceServicer):
    def GetProductReviews(self, request, context):
        logger.info(f"Receive GetProductReviews for product id:{request.product_id}")
        product_reviews = get_product_reviews(request.product_id)

        return product_reviews

    def GetProductReviewSummary(self, request, context):
        logger.info(f"Receive GetProductReviewSummary for product id:{request.product_id}")
        product_review_summary = get_product_review_summary(request.product_id)

        return product_review_summary

    def Check(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.SERVING)

    def Watch(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.UNIMPLEMENTED)

def get_product_reviews(request_product_id):

    with tracer.start_as_current_span("get_product_reviews") as span:

        span.set_attribute("app.product.id", request_product_id)

        product_reviews = demo_pb2.GetProductReviewsResponse()
        records = fetch_product_reviews_from_db(request_product_id)

        for row in records:
            logger.info(f"  username: {row[0]}, description: {row[1]}, score: {str(row[2])}")
            product_reviews.product_reviews.add(
                    username=row[0],
                    description=row[1],
                    score=str(row[2])
            )

        span.set_attribute("app.product_reviews.count", len(product_reviews.product_reviews))

        # Collect metrics for this service
        product_review_svc_metrics["app_product_review_counter"].add(len(product_reviews.product_reviews), {'product.id': request_product_id})

        return product_reviews

def get_product_review_summary(request_product_id):

    with tracer.start_as_current_span("get_product_review_summary") as span:

        span.set_attribute("app.product.id", request_product_id)
        product_review_summary = demo_pb2.GetProductReviewSummaryResponse()

        client = OpenAI(
            base_url=f"{llm_base_url}",
            # The OpenAI API requires an api_key to be present, but
            # our LLM doesn't use it
            api_key=f"{llm_api_key}"
        )

        user_prompt = f"Summarize the reviews for product ID:{request_product_id}. Use the database tool as needed to fetch the existing reviews."
        messages = [
           {"role": "system", "content": "You are a helpful assistant that creates a summary of product reviews."},
           {"role": "user", "content": user_prompt}
        ]

        # use the LLM to summarize the product reviews
        initial_response = client.chat.completions.create(
            model=llm_model,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        response_message = initial_response.choices[0].message
        tool_calls = response_message.tool_calls

        logger.info(f"Response message: {response_message}")

        # Check if the model wants to call a tool
        if tool_calls:
            tool_call = tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            logger.info(f"Model wants to call function: '{function_name}' with arguments: {function_args}")

            if function_name == "fetch_product_reviews":
                function_response = fetch_product_reviews(
                    product_id=function_args.get("product_id")
                )

                logger.info(f"Function response is: '{function_response}'")

                # Append the tool call and its result to the message history
                messages.append(response_message)  # Append the assistant's reply
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                    }
                )

                messages.append(
                    {
                        "role": "user",
                        "content": f"Summarize the reviews for product ID:{request_product_id} and avoid calling tools again."
                    }
                )

                logger.info(f"Invoking the LLM with the following messages: '{messages}'")

                final_response = client.chat.completions.create(
                    model=llm_model,
                    messages=messages,
                )

                result = final_response.choices[0].message.content

                # Load the result as a dictionary, then extract the average score
                result_dict = json.loads(result)
                average_score = str(result_dict['average_score'])
                summary = result_dict['product_review_summary']
                span.set_attribute("app.product_review.average_score", average_score)

                product_review_summary.average_score = average_score
                product_review_summary.product_review_summary = summary

                logger.info(f"Returning a product review summary: '{product_review_summary}'")

            else:
                raise Exception(f'Received unexpected tool call request: {function_name}')

        # Collect metrics for this service
        product_review_svc_metrics["app_product_review_summaries_counter"].add(1, {'product.id': request_product_id})

        return product_review_summary

def must_map_env(key: str):
    value = os.environ.get(key)
    if value is None:
        raise Exception(f'{key} environment variable must be set')
    return value


if __name__ == "__main__":
    service_name = must_map_env('OTEL_SERVICE_NAME')

    # Initialize Traces and Metrics
    tracer = trace.get_tracer_provider().get_tracer(service_name)
    meter = metrics.get_meter_provider().get_meter(service_name)

    product_review_svc_metrics = init_metrics(meter)

    # Initialize Logs
    logger_provider = LoggerProvider(
        resource=Resource.create(
            {
                'service.name': service_name,
            }
        ),
    )
    set_logger_provider(logger_provider)
    log_exporter = OTLPLogExporter(insecure=True)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)

    # Attach OTLP handler to logger
    logger = logging.getLogger('main')
    logger.addHandler(handler)

    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Add class to gRPC server
    service = ProductReviewService()
    demo_pb2_grpc.add_ProductReviewServiceServicer_to_server(service, server)
    health_pb2_grpc.add_HealthServicer_to_server(service, server)

    llm_base_url = must_map_env('LLM_BASE_URL')
    llm_api_key = must_map_env('OPENAI_API_KEY')
    llm_model = must_map_env('LLM_MODEL')

    # Start server
    port = must_map_env('PRODUCT_REVIEWS_PORT')
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f'Product reviews service started, listening on port {port}')
    server.wait_for_termination()
