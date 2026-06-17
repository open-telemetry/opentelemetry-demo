// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { initSDK } from '@embrace-io/web-sdk';
import type { ExtendedSpan } from '@embrace-io/web-sdk';
import { Span, SpanStatusCode, trace as otelTrace } from '@opentelemetry/api';

type AttributeValue = string | number | boolean;
type Attributes = Record<string, AttributeValue | undefined>;
type FrontendEnv = Record<string, string | undefined>;
type EmbraceSDK = Exclude<ReturnType<typeof initSDK>, false>;

interface ActiveSpan {
  embraceSpan?: ExtendedSpan;
  otelSpan: Span;
}

const activeSpans: Map<string, ActiveSpan> = new Map();
const tracerName = 'embrace-demo-flows';

let sdk: EmbraceSDK | undefined;
let initialized = false;
let missingConfigWarningShown = false;

function getWindowEnv(): FrontendEnv {
  if (typeof window === 'undefined') return {};

  return ((window as Window & { ENV?: FrontendEnv }).ENV || {});
}

function readEnv(key: string): string {
  const windowValue = getWindowEnv()[key];
  if (windowValue) return windowValue;

  return typeof process !== 'undefined' ? process.env[key] || '' : '';
}

function getEmbraceConfig() {
  const environment =
    readEnv('NEXT_PUBLIC_EMBRACE_ENVIRONMENT') ||
    readEnv('NEXT_PUBLIC_ENVIRONMENT') ||
    readEnv('NEXT_PUBLIC_PLATFORM') ||
    'local';

  return {
    appId: readEnv('NEXT_PUBLIC_EMBRACE_APP_ID'),
    appVersion:
      readEnv('NEXT_PUBLIC_EMBRACE_APP_VERSION') ||
      readEnv('NEXT_PUBLIC_APP_VERSION') ||
      'otel-demo-local',
    environment,
  };
}

function getStorageValue(storage: Storage | undefined, key: string): string | null {
  try {
    return storage?.getItem(key) || null;
  } catch {
    return null;
  }
}

function setStorageValue(storage: Storage | undefined, key: string, value: string): void {
  try {
    storage?.setItem(key, value);
  } catch {
    // Storage can be unavailable in restricted browser contexts.
  }
}

function captureSessionContext(appVersion: string, environment: string): Record<string, string> {
  const params = new URLSearchParams(window.location.search);
  const localStore = typeof localStorage !== 'undefined' ? localStorage : undefined;

  const runSource =
    params.get('run_source') ||
    getStorageValue(localStore, 'embrace_run_source') ||
    'organic';
  const persona =
    params.get('user_persona') ||
    params.get('persona') ||
    getStorageValue(localStore, 'embrace_persona') ||
    'new_visitor';
  const issue =
    params.get('issue') ||
    getStorageValue(localStore, 'embrace_issue') ||
    'none';
  const issueVariant =
    params.get('issue_variant') ||
    getStorageValue(localStore, 'embrace_issue_variant') ||
    'none';

  if (params.has('run_source')) setStorageValue(localStore, 'embrace_run_source', runSource);
  if (params.has('issue')) setStorageValue(localStore, 'embrace_issue', issue);
  if (params.has('user_persona') || params.has('persona')) {
    setStorageValue(localStore, 'embrace_persona', persona);
  }
  if (params.has('issue_variant')) {
    setStorageValue(localStore, 'embrace_issue_variant', issueVariant);
  }

  return {
    app_version: appVersion,
    environment,
    issue,
    issue_variant: issueVariant,
    run_source: runSource,
    user_persona: persona,
  };
}

function normalizeAttributes(attributes: Attributes = {}): Record<string, AttributeValue> {
  return Object.entries(attributes).reduce<Record<string, AttributeValue>>((result, [key, value]) => {
    if (value !== undefined) result[key] = value;
    return result;
  }, {});
}

function normalizeSpanAttributes(attributes: Attributes = {}): Record<string, string> {
  return Object.entries(attributes).reduce<Record<string, string>>((result, [key, value]) => {
    if (value !== undefined) result[key] = String(value);
    return result;
  }, {});
}

export function initEmbrace(): boolean {
  if (initialized || typeof window === 'undefined') return initialized;

  const { appId, appVersion, environment } = getEmbraceConfig();

  if (!appId) {
    if (!missingConfigWarningShown) {
      console.warn('[embrace] NEXT_PUBLIC_EMBRACE_APP_ID not set; skipping Embrace Web SDK init');
      missingConfigWarningShown = true;
    }
    return false;
  }

  const result = initSDK({
    appID: appId,
    appVersion,
    registerGlobally: false,
  });

  if (!result) {
    console.warn('[embrace] Embrace Web SDK init returned false');
    return false;
  }

  sdk = result;
  initialized = true;

  const context = captureSessionContext(appVersion, environment);
  Object.entries(context).forEach(([key, value]) => {
    try {
      sdk?.session.addProperty(key, value);
    } catch {
      // SDK context enrichment should never block app startup.
    }
  });

  return true;
}

export function addBreadcrumb(message: string): void {
  if (typeof window === 'undefined') return;

  try {
    sdk?.session.addBreadcrumb(message);
  } catch {
    // Breadcrumbs are best-effort telemetry.
  }
}

export function logError(message: string, attributes?: Attributes, error?: unknown): void {
  if (typeof window === 'undefined') return;

  try {
    const normalizedAttributes = normalizeAttributes(attributes);

    if (error) {
      sdk?.log.logException(error, {
        handled: true,
        attributes: {
          ...normalizedAttributes,
          log_message: message,
        },
      });
      return;
    }

    sdk?.log.message(message, 'error', {
      attributes: normalizedAttributes,
      includeStacktrace: true,
    });
  } catch {
    // Logging must not change app behavior.
  }
}

export function logWarning(message: string, attributes?: Attributes): void {
  if (typeof window === 'undefined') return;

  try {
    sdk?.log.message(message, 'warning', {
      attributes: normalizeAttributes(attributes),
    });
  } catch {
    // Logging must not change app behavior.
  }
}

export function startEmbraceSpan(name: string, attributes?: Attributes): void {
  if (typeof window === 'undefined' || activeSpans.has(name)) return;

  const otelSpan = otelTrace.getTracer(tracerName).startSpan(name, {
    attributes: normalizeAttributes(attributes),
  });

  let embraceSpan: ExtendedSpan | undefined;
  try {
    embraceSpan = sdk?.trace.startSpan(name, {
      attributes: normalizeSpanAttributes(attributes),
    });
  } catch {
    // The OTel span still preserves the existing frontend trace pipeline.
  }

  activeSpans.set(name, { embraceSpan, otelSpan });
}

export function endEmbraceSpan(name: string, success = true): void {
  const activeSpan = activeSpans.get(name);
  if (!activeSpan) return;

  const status = {
    code: success ? SpanStatusCode.OK : SpanStatusCode.ERROR,
    message: success ? undefined : `${name} failed`,
  };

  activeSpan.otelSpan.setStatus(status);
  activeSpan.otelSpan.end();

  try {
    if (success) {
      activeSpan.embraceSpan?.setStatus(status).end();
    } else {
      activeSpan.embraceSpan?.setStatus(status).fail({ code: 'failure' });
    }
  } catch {
    // The existing OTel span has already been ended.
  }

  activeSpans.delete(name);
}
