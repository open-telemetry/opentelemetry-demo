#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import logging
import os

import uvicorn

from demo_llm.server import create_app

logging.basicConfig(level=logging.INFO)


def instrument(app):
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        logging.warning(
            "opentelemetry-instrumentation-fastapi not installed, "
            "serving without HTTP request spans"
        )
        return
    FastAPIInstrumentor.instrument_app(app)


def main():
    app = create_app()
    instrument(app)
    port = int(os.getenv("DEMO_LLM_PORT", "8012"))
    logging.info("demo-llm serving OpenAI-compatible API on port %s", port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
