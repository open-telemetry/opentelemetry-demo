// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import InstrumentationMiddleware from '../../utils/telemetry/InstrumentationMiddleware';
import type { IAssistantMessage } from '../../types/Assistant';

const { ASSISTANT_ENABLED = '', AGENT_ADDR = '' } = process.env;

const AGENT_TIMEOUT_MS = 120000;

type TResponse = { reply: string } | { error: string } | '';

const toHistory = (history: unknown): IAssistantMessage[] =>
  Array.isArray(history)
    ? history
        .filter(
          (message): message is IAssistantMessage =>
            message !== null &&
            typeof message === 'object' &&
            (message.role === 'user' || message.role === 'assistant') &&
            typeof message.content === 'string'
        )
        .map(({ role, content }) => ({ role, content }))
    : [];

const handler = async ({ method, body }: NextApiRequest, res: NextApiResponse<TResponse>) => {
  if (ASSISTANT_ENABLED !== 'true' || !AGENT_ADDR) {
    return res.status(404).send('');
  }

  if (method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).send('');
  }

  const { message, history } = body ?? {};
  if (typeof message !== 'string' || !message.trim()) {
    return res.status(400).json({ error: 'message is required' });
  }

  const signal = AbortSignal.timeout(AGENT_TIMEOUT_MS);
  try {
    const response = await fetch(`http://${AGENT_ADDR}/prompt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history: toHistory(history) }),
      signal,
    });

    if (!response.ok) {
      return res.status(502).json({ error: 'The assistant is unavailable. Please try again.' });
    }

    const data = await response.json();
    const messages = data?.response?.messages;
    const lastMessage = Array.isArray(messages) ? messages[messages.length - 1] : undefined;
    if (
      (lastMessage?.type !== 'ai' && lastMessage?.role !== 'assistant') ||
      typeof lastMessage?.content !== 'string' ||
      !lastMessage.content.trim()
    ) {
      return res.status(502).json({ error: 'Agent returned an unexpected response' });
    }

    return res.status(200).json({ reply: lastMessage.content });
  } catch {
    return res.status(signal.aborted ? 504 : 502).json({ error: 'The assistant is unavailable. Please try again.' });
  }
};

export default InstrumentationMiddleware(handler);
