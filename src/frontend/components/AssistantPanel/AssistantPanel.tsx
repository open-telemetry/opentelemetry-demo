// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { FormEvent, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { ROOT_CONTEXT, SpanStatusCode, trace } from '@opentelemetry/api';
import ApiGateway from '../../gateways/Api.gateway';
import type { IAssistantMessage } from '../../types/Assistant';
import { CypressFields } from '../../utils/enums/CypressFields';
import * as S from './AssistantPanel.styled';

const tracer = trace.getTracer('frontend-web');
const subscribe = () => () => undefined;
const isAssistantEnabled = () => window.ENV?.NEXT_PUBLIC_ASSISTANT_ENABLED === 'true';
const serverSnapshot = () => false;

const AssistantPanel = () => {
  const isEnabled = useSyncExternalStore(subscribe, isAssistantEnabled, serverSnapshot);
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<IAssistantMessage[]>([]);
  const [pendingMessage, setPendingMessage] = useState('');
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const submittingRef = useRef(false);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, pendingMessage, isLoading]);

  useEffect(() => {
    if (isOpen && !isLoading) inputRef.current?.focus();
  }, [isOpen, isLoading]);

  const close = () => {
    setIsOpen(false);
    toggleRef.current?.focus();
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const message = input.trim();
    if (!message || submittingRef.current) return;

    const history = messages;
    submittingRef.current = true;
    setPendingMessage(message);
    setInput('');
    setError('');
    setIsLoading(true);

    return tracer.startActiveSpan('assistant.submit', {}, ROOT_CONTEXT, async span => {
      try {
        const { reply } = await ApiGateway.askAssistant(message, history);
        setMessages([...history, { role: 'user', content: message }, { role: 'assistant', content: reply }]);
      } catch {
        span.setStatus({ code: SpanStatusCode.ERROR });
        setInput(message);
        setError('The assistant could not answer. Please try again.');
      } finally {
        span.end();
        submittingRef.current = false;
        setPendingMessage('');
        setIsLoading(false);
      }
    });
  };

  if (!isEnabled) return null;

  return (
    <>
      <S.Toggle
        ref={toggleRef}
        data-cy={CypressFields.AssistantToggle}
        aria-expanded={isOpen}
        aria-controls="shop-assistant"
        onClick={() => setIsOpen(open => !open)}
      >
        Ask the assistant
      </S.Toggle>
      {isOpen && (
        <S.Panel
          id="shop-assistant"
          data-cy={CypressFields.AssistantPanel}
          aria-labelledby="shop-assistant-title"
          onKeyDown={event => {
            if (event.key === 'Escape') close();
          }}
        >
          <S.Header>
            <S.Title id="shop-assistant-title">Shop assistant</S.Title>
            <S.Close $type="link" aria-label="Close assistant" onClick={close}>
              ×
            </S.Close>
          </S.Header>
          <S.MessageList ref={listRef} role="log" aria-label="Conversation" aria-live="polite">
            {messages.length === 0 && !pendingMessage && (
              <S.Status>Ask about products, prices, shipping or your cart.</S.Status>
            )}
            {messages.map((message, index) => (
              <S.Message key={index} $role={message.role}>
                <span>{message.role === 'user' ? 'You: ' : 'Assistant: '}</span>
                {message.content}
              </S.Message>
            ))}
            {pendingMessage && <S.Message $role="user">{pendingMessage}</S.Message>}
            {isLoading && <S.Status role="status">Thinking...</S.Status>}
            {error && <S.Status role="alert">{error}</S.Status>}
          </S.MessageList>
          <S.Form onSubmit={onSubmit}>
            <S.Label htmlFor="assistant-question">Your question</S.Label>
            <S.Input
              ref={inputRef}
              id="assistant-question"
              value={input}
              onChange={event => setInput(event.target.value)}
              placeholder="Ask a question"
              disabled={isLoading}
            />
            <S.Send type="submit" disabled={isLoading || !input.trim()}>
              Send
            </S.Send>
          </S.Form>
        </S.Panel>
      )}
    </>
  );
};

export default AssistantPanel;
