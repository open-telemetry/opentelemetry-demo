#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import os

from openfeature import api
from openfeature.contrib.hook.opentelemetry import TracingHook
from openfeature.contrib.provider.flagd import FlagdProvider

api.set_provider(
    FlagdProvider(
        host=os.environ.get("FLAGD_HOST", "flagd"),
        port=int(os.environ.get("FLAGD_PORT", 8013)),
    )
)
api.add_hooks([TracingHook()])


def get_int_feature_flag(flag_name: str, default: int = 0) -> int:
    client = api.get_client()
    return client.get_integer_value(flag_name, default)
