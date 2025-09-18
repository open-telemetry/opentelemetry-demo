#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import logging
import sys
from pythonjsonlogger import jsonlogger
from opentelemetry import trace


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # Add OpenTelemetry trace context
        current_span = trace.get_current_span()
        span_context = current_span.get_span_context()
        
        if not log_record.get('otelTraceID'):
            log_record['otelTraceID'] = trace.format_trace_id(span_context.trace_id)
        if not log_record.get('otelSpanID'):
            log_record['otelSpanID'] = trace.format_span_id(span_context.span_id)
        
        # Add consistent trace context fields
        log_record['traceId'] = trace.format_trace_id(span_context.trace_id)
        log_record['spanId'] = trace.format_span_id(span_context.span_id)
        log_record['traceFlags'] = span_context.trace_flags
        log_record['service'] = 'recommendation-service'
        log_record['timestamp'] = record.created

def getJSONLogger(name):
    logger = logging.getLogger(name)
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter('%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
