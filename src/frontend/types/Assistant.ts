/**
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

export interface IAssistantMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface IAssistantReply {
  reply: string;
}
