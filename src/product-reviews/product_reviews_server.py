#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


# Python
import os
from concurrent import futures
import random

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
from opentelemetry.trace import Status, StatusCode

# Local
import logging
import demo_pb2
import demo_pb2_grpc
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc
from database import fetch_product_reviews, fetch_product_reviews_from_db, fetch_avg_product_review_score_from_db

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider

from metrics import (
    init_metrics
)

# OpenAI
from openai import OpenAI

llm_host = None
llm_port = None
llm_mock_url = None
llm_base_url = None
llm_api_key = None
llm_model = None

class ProductReviewService(demo_pb2_grpc.ProductReviewServiceServicer):
    def GetProductReviews(self, request, context):
        logger.info(f"Receive GetProductReviews for product id:{request.product_id}")
        product_reviews = get_product_reviews(request.product_id)

        return product_reviews

    def GetAverageProductReviewScore(self, request, context):
        logger.info(f"Receive GetAverageProductReviewScore for product id:{request.product_id}")
        product_reviews = get_average_product_review_score(request.product_id)

        return product_reviews

    def AskProductAIAssistant(self, request, context):
        logger.info(f"Receive AskProductAIAssistant for product id:{request.product_id}, question: {request.question}")
        ai_assistant_response = get_ai_assistant_response(request.product_id, request.question)

        return ai_assistant_response

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

def get_average_product_review_score(request_product_id):

    with tracer.start_as_current_span("get_average_product_review_score") as span:

        span.set_attribute("app.product.id", request_product_id)

        product_review_score = demo_pb2.GetAverageProductReviewScoreResponse()
        avg_score = fetch_avg_product_review_score_from_db(request_product_id)
        product_review_score.average_score = avg_score

        span.set_attribute("app.product_reviews.average_score", avg_score)

        return product_review_score

def get_ai_assistant_response(request_product_id, question):

    with tracer.start_as_current_span("get_ai_assistant_response") as span:

        ai_assistant_response = demo_pb2.AskProductAIAssistantResponse()

        span.set_attribute("app.product.id", request_product_id)
        span.set_attribute("app.product.question", question)

        llm_rate_limit_error = check_feature_flag("llmRateLimitError")
        logger.info(f"llmRateLimitError feature flag: {llm_rate_limit_error}")
        if llm_rate_limit_error:
            random_number = random.random()
            logger.info(f"Generated a random number: {str(random_number)}")
            # return a rate limit error 50% of the time
            if random_number < 0.5:

                client = OpenAI(
                    base_url=f"{llm_mock_url}",
                    api_key=f"{llm_api_key}"
                )

                messages = [
                   {"role": "system", "content": "You are a helpful assistant."},
                   {"role": "user", "content": f"Answer about product ID:{request_product_id}: {question}"}
                ]
                logger.info(f"Invoking LLM with model: {llm_model}-rate-limit")

                try:
                    client.chat.completions.create(
                        model=f"{llm_model}-rate-limit",
                        messages=messages,
                    )
                except Exception as e:
                    logger.error(f"Caught Exception: {e}")
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, description=str(e)))
                    ai_assistant_response.response = "The system is unable to process your response. Please try again later."
                    return ai_assistant_response

        # Fetch product reviews from DB directly
        reviews_data = fetch_product_reviews(product_id=request_product_id)
        logger.info(f"Fetched product reviews: '{reviews_data}'")

        # Build a direct prompt with review data in context
        client = OpenAI(
            base_url=f"{llm_base_url}",
            api_key=f"{llm_api_key}"
        )

        system_content = "You are a helpful assistant that summarizes product reviews. Keep the response brief with no more than 1-2 sentences. If you don't know the answer, just say you don't know."
        user_prompt = f"Here are the reviews for product {request_product_id}:\n{reviews_data}\n\nQuestion: {question}"

        messages = [
           {"role": "system", "content": system_content},
           {"role": "user", "content": user_prompt}
        ]

        logger.info(f"Invoking the LLM with messages: '{messages}'")

        response = client.chat.completions.create(
            model=llm_model,
            messages=messages,
        )

        result = response.choices[0].message.content
        ai_assistant_response.response = result

        logger.info(f"Returning an AI assistant response: '{result}'")

        # Collect metrics for this service
        product_review_svc_metrics["app_ai_assistant_counter"].add(1, {'product.id': request_product_id})

        return ai_assistant_response

def must_map_env(key: str):
    value = os.environ.get(key)
    if value is None:
        raise Exception(f'{key} environment variable must be set')
    return value

def check_feature_flag(flag_name: str):
    # Initialize OpenFeature
    client = api.get_client()
    return client.get_boolean_value(flag_name, False)

if __name__ == "__main__":
    service_name = must_map_env('OTEL_SERVICE_NAME')

    api.set_provider(FlagdProvider(host=os.environ.get('FLAGD_HOST', 'flagd'), port=os.environ.get('FLAGD_PORT', 8013)))

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

    llm_host = must_map_env('LLM_HOST')
    llm_port = must_map_env('LLM_PORT')
    llm_mock_url = f"http://{llm_host}:{llm_port}/v1"
    llm_base_url = must_map_env('LLM_BASE_URL')
    llm_api_key = must_map_env('OPENAI_API_KEY')
    llm_model = must_map_env('LLM_MODEL')

    # Start server
    port = must_map_env('PRODUCT_REVIEWS_PORT')
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f'Product reviews service started, listening on port {port}')
    server.wait_for_termination()
