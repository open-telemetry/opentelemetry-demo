#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

def init_metrics(meter):

    # Product reviews counter
    app_product_review_counter = meter.create_counter(
        'app_product_review_counter', unit='reviews', description="Counts the total number of returned product reviews"
    )

    # Product review summaries counter
    app_product_review_summaries_counter = meter.create_counter(
        'app_product_review_summaries_counter', unit='summaries', description="Counts the total number of generated product review summaries"
    )

    product_review_svc_metrics = {
        "app_product_review_counter": app_product_review_counter,
        "app_product_review_summaries_counter": app_product_review_summaries_counter,
    }

    return product_review_svc_metrics
