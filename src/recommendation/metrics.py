#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

def init_metrics(meter):

    # Recommendations counter
    recommendation_requests = meter.create_counter(
        'demo.recommendation.requests', unit='recommendations', description="Counts the total number of given recommendations"
    )

    rec_svc_metrics = {
        "demo.recommendation.requests": recommendation_requests,
    }

    return rec_svc_metrics
