// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { Span } from '@opentelemetry/api';
import { CompositePropagator, W3CBaggagePropagator, W3CTraceContextPropagator } from '@opentelemetry/core';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { FetchTransport, getWebInstrumentations, initializeFaro, type Faro } from '@grafana/faro-web-sdk';
import { TracingInstrumentation } from '@grafana/faro-web-tracing';
import Router from 'next/router';
import SessionGateway from '../../gateways/Session.gateway';
import frontendPackage from '../../package.json';

type Session = ReturnType<typeof SessionGateway.getSession>;

let faroInstance: Faro | undefined;
let currentViewKey = '';
let currentViewId = '';

const buildFaroUser = (session: Session) => ({
  id: session.userId,
  email: session.userEmail,
  username: session.userName,
});

const getFrontendPageId = () => {
  if (Router.router?.pathname) {
    return Router.router.pathname;
  }

  return window.location.pathname || '/';
};

const getViewId = () => {
  const viewKey = window.location.href;

  if (viewKey !== currentViewKey || !currentViewId) {
    currentViewKey = viewKey;
    currentViewId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  return currentViewId;
};

const getFrontendPageMeta = () => ({
  page: {
    id: getFrontendPageId(),
    url: window.location.href,
    attributes: {
      view_id: getViewId(),
    },
  },
});

const setPageId = (span: Span) => {
  const pageId = faroInstance?.api.getPage()?.id;

  if (pageId) {
    span.setAttribute('page.id', pageId);
  }
};

const FrontendTracer = (session?: Session) => {
  if (typeof window === 'undefined') {
    return faroInstance;
  }

  const currentSession = session ?? SessionGateway.getSession();
  if (faroInstance) {
    faroInstance.api.setSession({ id: currentSession.userId });
    faroInstance.api.setUser(buildFaroUser(currentSession));
    return faroInstance;
  }

  const {
    NEXT_PUBLIC_FARO_URL = '',
    NEXT_PUBLIC_FARO_API_KEY = '',
    NEXT_PUBLIC_FARO_APP_NAME = 'frontend-web',
  } = window.ENV ?? {};

  if (!NEXT_PUBLIC_FARO_URL || !NEXT_PUBLIC_FARO_API_KEY) {
    return undefined;
  }

  faroInstance = initializeFaro({
    app: {
      name: NEXT_PUBLIC_FARO_APP_NAME || 'frontend-web',
      version: frontendPackage.version,
    },
    ignoreUrls: [NEXT_PUBLIC_FARO_URL],
    pageTracking: {
      generatePageId: getFrontendPageId,
    },
    sessionTracking: {
      session: {
        id: currentSession.userId,
      },
      generateSessionId: () => currentSession.userId,
    },
    user: buildFaroUser(currentSession),
    transports: [
      new FetchTransport({
        url: NEXT_PUBLIC_FARO_URL,
        requestOptions: {
          headers: {
            Authorization: `Bearer ${NEXT_PUBLIC_FARO_API_KEY}`,
          },
        },
      }),
    ],
    instrumentations: [
      ...getWebInstrumentations({ captureConsole: true }),
      new TracingInstrumentation({
        contextManager: new ZoneContextManager(),
        propagator: new CompositePropagator({
          propagators: [new W3CBaggagePropagator(), new W3CTraceContextPropagator()],
        }),
        instrumentationOptions: {
          propagateTraceHeaderCorsUrls: [/.*/],
          fetchInstrumentationOptions: {
            applyCustomAttributesOnSpan: setPageId,
          },
          xhrInstrumentationOptions: {
            applyCustomAttributesOnSpan: setPageId,
          },
        },
      }),
    ],
  });

  faroInstance.metas.add(getFrontendPageMeta);

  return faroInstance;
};

export default FrontendTracer;
