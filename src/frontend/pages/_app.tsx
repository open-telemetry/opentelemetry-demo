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
import { init, identify, addSignalAttribute } from '@dash0/sdk-web';
import { createRandomUser } from '../utils/faker/createRandomUser';
import { createRandomLocation } from '../utils/faker/createRandomLocation';

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

    additionalSignalAttributes: {
      'user_agent.original': randomUser.userAgent,
    },

    serviceName: window.ENV.NEXT_PUBLIC_OTEL_SERVICE_NAME!,
    endpoint: {
      // Replace this with the endpoint url identified during preparation
      url: window.ENV.NEXT_PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT!.replace('/v1/traces', ''),
      // Replace this with your auth token you created earlier
      // Ideally inject the value at build time to not commit the token to git, even if its effectively public
      authToken: '<YOUR_TOKEN>',
    },
  });

  if (Math.floor(Math.random() * 8) > 1) {
    identify('user_' + Math.random().toString(16).substr(2, 8), randomUser);

    // TODO: this doesnt work :(
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
