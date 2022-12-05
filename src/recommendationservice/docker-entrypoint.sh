#!/bin/sh
set -e

# install the sentry SDK in editable mode, for local development
python -m pip install -e /sentry-python

# start recommendation service
opentelemetry-instrument python recommendation_server.py
