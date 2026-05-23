#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

def init_metrics(meter):

    # Product reviews counter
    product_review_requests = meter.create_counter(
        'demo.product.review.requests', unit='reviews', description="Counts the total number of returned product reviews"
    )

    # AI Assistant counter
    ai_assistant_requests = meter.create_counter(
        'demo.product.ai_assistant.requests', unit='summaries', description="Counts the total number of AI Assistant requests"
    )

    product_review_svc_metrics = {
        "demo.product.review.requests": product_review_requests,
        "demo.product.ai_assistant.requests": ai_assistant_requests,
    }

    return product_review_svc_metrics
