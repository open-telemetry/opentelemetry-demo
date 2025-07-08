// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import '../styles/globals.css';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App, { AppContext, AppProps } from 'next/app';
import { getCookie } from 'cookies-next';
import CurrencyProvider from '../providers/Currency.provider';
import CartProvider from '../providers/Cart.provider';
import { ThemeProvider } from 'styled-components';
import Theme from '../styles/Theme';
import FrontendTracer from '../utils/telemetry/FrontendTracer';
import { init, identify, addSignalAttribute, removeSignalAttribute } from '@dash0/sdk-web';
import { createRandomUser } from '../utils/faker/createRandomUser';
import { createRandomLocation } from '../utils/faker/createRandomLocation';

declare global {
  interface Window {
    ENV: {
      NEXT_PUBLIC_PLATFORM?: string;
      NEXT_PUBLIC_OTEL_SERVICE_NAME?: string;
      NEXT_PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT?: string;
      IS_SYNTHETIC_REQUEST?: string;
      NEXT_PUBLIC_DASH0_WEB_SDK_URL: string;
    };
  }
}

if (typeof window !== 'undefined') {
  const collector = getCookie('otelCollectorUrl')?.toString() || '';
  FrontendTracer(collector);
}

if (typeof window !== 'undefined') {
  /**
   * NOTE: This instrumentation is mostly focused on creating random user data and is not how the Dash0 Web SDK should be used.
   */
  const randomUser = createRandomUser();

  init({
    pageViewInstrumentation: {
      includeParts: ['SEARCH', 'HASH'],
    },
    serviceName: window.ENV.NEXT_PUBLIC_OTEL_SERVICE_NAME!,
    endpoint: {
      url: window.ENV.NEXT_PUBLIC_DASH0_WEB_SDK_URL,
      // We provide an empty token, because since we're using a proxy, there's no need for an actual token here.
      authToken: '',
    },
  });

  if (Math.floor(Math.random() * 8) > 1) {
    identify('user_' + Math.random().toString(16).substr(2, 8), randomUser);

    // Removing the automatically set user_agent
    removeSignalAttribute('user_agent.original');
    // So that we can add our own faked one.
    addSignalAttribute('user_agent.original', randomUser.userAgent);

    for (const [key, value] of Object.entries(createRandomLocation())) {
      addSignalAttribute(key, value);
    }
  }
}

const queryClient = new QueryClient();

function MyApp({ Component, pageProps }: AppProps) {
  return (
    <ThemeProvider theme={Theme}>
      <QueryClientProvider client={queryClient}>
        <CurrencyProvider>
          <CartProvider>
            <Component {...pageProps} />
          </CartProvider>
        </CurrencyProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

MyApp.getInitialProps = async (appContext: AppContext) => {
  const appProps = await App.getInitialProps(appContext);

  return { ...appProps };
};

export default MyApp;
