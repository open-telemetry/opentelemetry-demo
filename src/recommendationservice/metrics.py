#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

def init_metrics(meter):

    # Recommendations counter
    app_recommendations_counter = meter.create_counter(
        'app_recommendations_counter', unit='recommendations', description="Counts the total number of given recommendations"
    )

    app_recommendations_cache_size_counter = meter.create_counter(
        'app_recommendations_cache_size', unit='cache_size', description="Counts the total number of items in the cache"
    )

    rec_svc_metrics = {
        "app_recommendations_counter": app_recommendations_counter,
        "app_recommendations_cache_size": app_recommendations_cache_size_counter,
    }

    return rec_svc_metrics
