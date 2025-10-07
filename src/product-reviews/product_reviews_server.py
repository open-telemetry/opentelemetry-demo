#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


# Python
import os
import random
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

# MySQL
import mysql.connector
from mysql.connector import Error

db_host = None
db_port = None
db_user = None
db_password = None
db_name = None

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

    product_reviews = demo_pb2.GetProductReviewsResponse()
    fetch_product_reviews_from_db(request_product_id, product_reviews)

    return product_reviews

def fetch_product_reviews_from_db(request_product_id, product_reviews):
    logger.info("Received a request to fetch product reviews from the database.")
    try:
        with mysql.connector.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name
        ) as connection:
            logger.info("Successfully connected to the database.")

            with connection.cursor() as cursor:
                # Define the SQL query
                query = "SELECT username, description, score FROM productreviews WHERE product_id= %s"

                # Execute the query
                cursor.execute(query, (request_product_id, ))

                # Fetch all the rows from the query result
                records = cursor.fetchall()

                logger.info(f"Found {cursor.rowcount} product reviews(s):")

                # Add each row to the list of product reviews
                for row in records:
                    logger.info(f"  username: {row[0]}, description: {row[1]}, score: {row[2]}")
                    review = product_reviews.product_reviews.add(
                            username=row[0],
                            description=row[1],
                            score=row[2]
                    )

    except Error as e:
        logger.error(f"Error connecting to MySQL or executing query: {e}")

def get_product_review_summary(request_product_id):

    product_review_summary = demo_pb2.GetProductReviewSummaryResponse()
    product_review_summary.product_review_summary = "This is an AI-generated summary"

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

    # Retrieve MySQL environment variables
    db_host = must_map_env('MYSQL_HOST')
    db_port = must_map_env('MYSQL_PORT')
    db_user = must_map_env('MYSQL_USER')
    db_password = must_map_env('MYSQL_PASSWORD')
    db_name = must_map_env('MYSQL_DATABASE')

    # Start server
    port = must_map_env('PRODUCT_REVIEWS_PORT')
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f'Product reviews service started, listening on port {port}')
    server.wait_for_termination()
