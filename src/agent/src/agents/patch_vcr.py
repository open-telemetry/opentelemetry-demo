#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
from difflib import SequenceMatcher

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
    status_code = response.get("status", {}).get("code")
    if status_code is not None and not (200 <= int(status_code) < 300):
        logging.warning("VCR: not recording response (HTTP %s)", status_code)
        return None

    response["headers"] = {}
    try:
        body = response.get("body", {}).get("string")
        if isinstance(body, bytes):
            body = body.decode("utf-8")

        data = json.loads(body)

        if isinstance(data, dict) and "error" in data and "choices" not in data:
            logging.warning(
                "VCR: not recording response (provider error payload)"
            )
            return None
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


# When MCP is enabled, tool schemas and tool-result messages are wrapped
# differently than the built-in tools, so the request body sent to the LLM
# differs slightly to the recorded request. Exact body matching then misses the
# cassette. This threshold controls how close a recorded request must be to
# live one for it to be a match. 1.0 == exact; lower == fuzzier.
VCR_MATCH_THRESHOLD = float(os.getenv("VCR_MATCH_THRESHOLD", "0.85"))


def _parse_body(request):
    """Parse a request body into a dict, or None if it isn't JSON."""
    body = getattr(request, "body", None)
    if body is None:
        return None
    if hasattr(body, "decode"):
        try:
            body = body.decode("utf-8")
        except Exception:
            return None
    try:
        return json.loads(body)
    except Exception:
        return None


def _unwrap_tool_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", block.get("content", ""))))
            else:
                parts.append(str(block))
        return "".join(parts)
    return _stringify(content)


def _normalize_message(msg):
    if isinstance(msg, dict) and msg.get("role") == "tool":
        normalized = dict(msg)
        normalized["content"] = _unwrap_tool_content(msg.get("content"))
        return normalized
    return msg


def _stringify(value):
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True)
    except Exception:
        return str(value)


def body_similarity(r1, r2):
    """Return a similarity score in [0, 1] between two LLM request bodies.

      * requests with a different number of messages never match (score 0),
        which prevents replaying an earlier turn's response;
      * the newest message is weighted most heavily, since that is what
        actually changes between otherwise-identical requests.

    Falls back to a whole-body ratio when either body isn't JSON with a
    ``messages`` list (e.g. embeddings or other endpoints).
    """
    d1 = _parse_body(r1)
    d2 = _parse_body(r2)

    m1 = d1.get("messages") if isinstance(d1, dict) else None
    m2 = d2.get("messages") if isinstance(d2, dict) else None

    if not isinstance(m1, list) or not isinstance(m2, list):
        # Whole-body fallback for non-chat requests.
        return SequenceMatcher(None, _stringify(d1), _stringify(d2)).ratio()

    if len(m1) != len(m2):
        return 0.0

    if not m1:
        return 1.0

    n1 = [_normalize_message(m) for m in m1]
    n2 = [_normalize_message(m) for m in m2]

    full_ratio = SequenceMatcher(None, _stringify(n1), _stringify(n2)).ratio()
    last_ratio = SequenceMatcher(
        None, _stringify(n1[-1]), _stringify(n2[-1])
    ).ratio()
    # Adding more weight to the recent message
    return 0.4 * full_ratio + 0.6 * last_ratio


def similar_body_matcher(r1, r2):
    """Fuzzy, turn-aware body matcher for VCR.

    Requests match when identical or when their similarity meets
    VCR_MATCH_THRESHOLD, letting the agent replay a recorded LLM response even
    when the live request differs slightly (e.g. MCP-wrapped tool results).
    """
    score = body_similarity(r1, r2)
    if score >= VCR_MATCH_THRESHOLD:
        return
    raise AssertionError(
        f"request bodies differ beyond threshold "
        f"(score={score:.4f} < {VCR_MATCH_THRESHOLD:.4f})"
    )


VCR = vcr.VCR(
    cassette_library_dir="fixtures/vcr_cassettes",
    record_mode="new_episodes",
    serializer="yaml",
    path_transformer=vcr.VCR.ensure_suffix(".yaml"),
    filter_headers=["authorization", "x-api-key", "api-key"],
    match_on=["similar_body"],
    before_record_request=normalize_body,
    before_record_response=clean_response,
    decode_compressed_response=True,
)
VCR.register_matcher("similar_body", similar_body_matcher)


# vcrpy's by default returns the FIRST recorded request that matches. With
# a fuzzy matcher several recordings may clear the threshold.
# Patch playback to instead return the CLOSEST match.
def _install_best_match_playback():
    from vcr.cassette import Cassette
    from vcr.errors import UnhandledHTTPRequestError

    def play_response(self, request):
        best_idx = None
        best_score = -1.0
        for idx, recorded in enumerate(self.requests):
            if self.play_counts[idx] > 0:
                continue
            try:
                score = body_similarity(recorded, request)
            except Exception:
                score = 0.0
            if score >= VCR_MATCH_THRESHOLD and score > best_score:
                best_score = score
                best_idx = idx
        if best_idx is None:
            raise UnhandledHTTPRequestError(
                f"No unplayed cassette request within threshold "
                f"({VCR_MATCH_THRESHOLD:.4f}) for {request}"
            )
        self.play_counts[best_idx] += 1
        logging.info(
            "VCR best-match playback: entry %d (score=%.4f)",
            best_idx,
            best_score,
        )
        return self.responses[best_idx]

    Cassette.play_response = play_response


if use_vcr:
    try:
        _install_best_match_playback()
    except Exception as e:
        logging.error("Could not install best-match VCR playback: %s", e)
