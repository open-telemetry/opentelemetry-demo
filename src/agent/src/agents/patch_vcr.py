#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os

import vcr
import vcr.stubs.httpx_stubs

logging.getLogger("vcr").setLevel(logging.ERROR)


# Cassette bodies are stored as plain JSON strings (see clean_response) for
# human-readable, diffable fixtures. httpx.ByteStream requires bytes, so
# encode the body back to bytes before vcrpy reconstructs the response for
# playback; without this, replay raises a TypeError deep in httpx's async
# body reader.
_original_deserialize_response = vcr.stubs.httpx_stubs._deserialize_response


def patched_deserialize_response(vcr_response, httpx_module):
    body = vcr_response.get("body", {}).get("string")
    if isinstance(body, str):
        vcr_response["body"]["string"] = body.encode("utf-8")
    return _original_deserialize_response(vcr_response, httpx_module)


use_vcr = os.getenv("USE_VCR", "False").lower() == "true"
if use_vcr:
    vcr.stubs.httpx_stubs._deserialize_response = patched_deserialize_response


def normalize_body(request):
    try:
        if request.body:
            encoding = "utf-8"
            if hasattr(request.body, "decode"):
                data = json.loads(request.body.decode(encoding))
            else:
                data = json.loads(request.body)
            request.body = json.dumps(data, sort_keys=True).encode(encoding)
            request.headers = {}
            request.uri = "https://vcr.local/"
            request.method = "POST"
    except Exception:
        pass
    return request


def clean_response(response):
    response["headers"] = {}
    try:
        body = response.get("body", {}).get("string")
        if isinstance(body, bytes):
            body = body.decode("utf-8")

        data = json.loads(body)
        # id/created are required by the openai response schema, so they are
        # normalized to fixed values instead of removed, keeping fixtures
        # deterministic without failing response validation on replay.
        if "id" in data:
            data["id"] = "chatcmpl-fixture"
        if "created" in data:
            data["created"] = 0
        for key in [
            "system_fingerprint",
            "usage",
            "prompt_filter_results",
            "service_tier",
        ]:
            data.pop(key, None)

        for choice in data.get("choices", []):
            choice.pop("provider_specific_fields", None)
            message = choice.get("message", {})
            message.pop("provider_specific_fields", None)
            message.pop("annotations", None)

        response["body"]["string"] = json.dumps(data, sort_keys=True)
    except Exception:
        pass
    return response


VCR = vcr.VCR(
    cassette_library_dir="fixtures/vcr_cassettes",
    record_mode="new_episodes",
    serializer="yaml",
    path_transformer=vcr.VCR.ensure_suffix(".yaml"),
    filter_headers=["authorization", "x-api-key", "api-key"],
    match_on=["body"],
    before_record_request=normalize_body,
    before_record_response=clean_response,
    decode_compressed_response=True,
)
