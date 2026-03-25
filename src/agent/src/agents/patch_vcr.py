#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json
import logging

import vcr
import vcr.stubs.httpx_stubs

logging.getLogger("vcr").setLevel(logging.ERROR)


async def patched_to_serialized_response(response, aread=False):
    if hasattr(response, "_decoder"):
        del response._decoder

    if aread:
        content = await response.aread()
    else:
        content = response.read()

    return {
        "status": {"code": response.status_code, "message": response.reason_phrase},
        "headers": dict(response.headers),
        "body": {"string": content},
    }


vcr.stubs.httpx_stubs._to_serialized_response = patched_to_serialized_response


def normalize_body(request):
    try:
        if request.body:
            encoding = "utf-8"
            if hasattr(request.body, "decode"):
                data = json.loads(request.body.decode(encoding))
            else:
                data = json.loads(request.body)
            request.body = json.dumps(data, sort_keys=True).encode(encoding)
    except Exception:
        pass
    return request


def clean_response(response):
    headers = response["headers"]
    headers.pop("content-encoding", None)
    headers.pop("transfer-encoding", None)
    return response


VCR = vcr.VCR(
    cassette_library_dir="fixtures/vcr_cassettes",
    record_mode="new_episodes",
    serializer="yaml",
    path_transformer=vcr.VCR.ensure_suffix(".yaml"),
    filter_headers=["authorization", "x-api-key", "api-key"],
    match_on=["method", "uri", "body"],
    before_record_request=normalize_body,
    before_record_response=clean_response,
    decode_compressed_response=True,
)
