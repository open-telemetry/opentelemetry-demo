# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from google.cloud.aiplatform_v1.types import (
    GenerateContentRequest as v1GenerateContentRequest,
)
from google.cloud.aiplatform_v1beta1.types import (
    GenerateContentRequest,
)
from langchain_core.messages import (
    BaseMessage,
)
from langchain_google_vertexai import ChatVertexAI


class PatchedChatVertexAI(ChatVertexAI):
    def _prepare_request_gemini(
        self, messages: list[BaseMessage], *args: Any, **kwargs: Any
    ) -> v1GenerateContentRequest | GenerateContentRequest:
        # See https://github.com/langchain-ai/langchain-google/issues/886
        #
        # Filter out any blocked messages with no content which can appear if you have a blocked
        # message from finish_reason SAFETY:
        #
        # AIMessage(
        #     content="",
        #     additional_kwargs={},
        #     response_metadata={
        #         "is_blocked": True,
        #         "safety_ratings": [ ... ],
        #         "finish_reason": "SAFETY",
        #     },
        #     ...
        # )
        #
        # These cause `google.api_core.exceptions.InvalidArgument: 400 Unable to submit request
        # because it must include at least one parts field`

        messages = [
            message
            for message in messages
            if not message.response_metadata.get("is_blocked", False)
        ]
        return super()._prepare_request_gemini(messages, *args, **kwargs)
