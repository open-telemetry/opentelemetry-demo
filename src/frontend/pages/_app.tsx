// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import '../styles/globals.css';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App, { AppContext, AppProps } from 'next/app';
import { useEffect } from 'react';
import CurrencyProvider from '../providers/Currency.provider';
import CartProvider from '../providers/Cart.provider';
import { ThemeProvider } from 'styled-components';
import Theme from '../styles/Theme';
import FrontendTracer from '../utils/telemetry/FrontendTracer';
import SessionGateway from '../gateways/Session.gateway';
import { OpenFeatureProvider, OpenFeature } from '@openfeature/react-sdk';
import { FlagdWebProvider } from '@openfeature/flagd-web-provider';

declare global {
  interface Window {
    ENV: {
      NEXT_PUBLIC_PLATFORM?: string;
      NEXT_PUBLIC_OTEL_SERVICE_NAME?: string;
      NEXT_PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT?: string;
      IS_SYNTHETIC_REQUEST?: string;
    };
  }
}

const queryClient = new QueryClient();
let appInitialized = false;

function MyApp({ Component, pageProps }: AppProps) {
  useEffect(() => {
    if (appInitialized || typeof window === 'undefined' || !window.location) {
      return;
    }

    appInitialized = true;

    const initializeApp = async () => {
      await FrontendTracer();

      const session = SessionGateway.getSession();

      // Set context prior to provider init to avoid multiple HTTP calls.
      await OpenFeature.setContext({ targetingKey: session.userId, ...session });

      const useTLS = window.location.protocol === 'https:';
      const port = window.location.port ? parseInt(window.location.port, 10) : useTLS ? 443 : 80;

      await OpenFeature.setProvider(
        new FlagdWebProvider({
          host: window.location.hostname,
          pathPrefix: 'flagservice',
          port,
          tls: useTLS,
          maxRetries: 3,
          maxDelay: 10000,
        })
      );
    };

    initializeApp().catch(error => {
      appInitialized = false;
      console.error('Failed to initialize frontend telemetry and feature flags', error);
    });
  }, []);

  return (
    <ThemeProvider theme={Theme}>
      <OpenFeatureProvider>
        <QueryClientProvider client={queryClient}>
          <CurrencyProvider>
            <CartProvider>
              <Component {...pageProps} />
            </CartProvider>
          </CurrencyProvider>
        </QueryClientProvider>
      </OpenFeatureProvider>
    </ThemeProvider>
  );
}

MyApp.getInitialProps = async (appContext: AppContext) => {
  const appProps = await App.getInitialProps(appContext);

  return { ...appProps };
};

export default MyApp;
