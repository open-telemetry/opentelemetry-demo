// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { Span, SpanProcessor } from "@opentelemetry/sdk-trace";
import SessionGateway from "../../gateways/Session.gateway";
import { AttributeNames } from "../enums/AttributeNames";

const { userId } = SessionGateway.getSession();

export class SessionIdProcessor implements SpanProcessor {
    forceFlush(): Promise<void> {
        return Promise.resolve();
    }

    onStart(span: Span): void {
        span.setAttribute(AttributeNames.SESSION_ID, userId);
        span.setAttribute(AttributeNames.ENDUSER_ID, userId);
    }

    onEnd(): void {}

    shutdown(): Promise<void> {
        return Promise.resolve();
    }
}
