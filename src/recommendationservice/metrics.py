#!/usr/bin/python

# from gc import callbacks
# from typing import Iterable
# import psutil


def init_metrics(meter):

    # Requests counter
    list_recommendations_request_counter = meter.create_counter(
        name="app_recommendations_request_counter",
        description="number of requests to RecommendationService.ListRecommendations",
        unit="requests"
    )

    # Recommendations counter
    app_recommendations_counter = meter.create_counter(
        'app_recommendations_counter', unit='recommendations', description="Counts the total number of given recommendations"
    )

    attributes = {"application.name": "otel-demo"}

    rec_svc_metrics = {
        "list_recommendations_request_counter": list_recommendations_request_counter,
        "attributes": attributes,
        "app_recommendations_counter": app_recommendations_counter,
    }

    return rec_svc_metrics
