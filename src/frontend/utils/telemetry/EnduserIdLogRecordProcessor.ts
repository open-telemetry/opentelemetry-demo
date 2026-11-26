// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { LogRecordProcessor, ReadWriteLogRecord } from "@opentelemetry/sdk-logs";
import SessionGateway from "../../gateways/Session.gateway";
import { AttributeNames } from "../enums/AttributeNames";

const { userId } = SessionGateway.getSession();

export class EnduserIdLogRecordProcessor implements LogRecordProcessor {
    forceFlush(): Promise<void> {
        return Promise.resolve();
    }

    onEmit(logRecord: ReadWriteLogRecord): void {
        logRecord.setAttribute(AttributeNames.ENDUSER_ID, userId);
    }

    shutdown(): Promise<void> {
        return Promise.resolve();
    }
}
