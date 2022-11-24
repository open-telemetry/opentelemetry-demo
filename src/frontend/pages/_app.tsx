import '../styles/globals.css';
import { QueryClient, QueryClientProvider } from 'react-query';
import App, { AppContext, AppProps } from 'next/app';
import { getCookie } from 'cookies-next';
import CurrencyProvider from '../providers/Currency.provider';
import CartProvider from '../providers/Cart.provider';
import { ThemeProvider } from 'styled-components';
import Theme from '../styles/Theme';
import Faro from '../utils/telemetry/FaroTracer';

declare global {
  interface Window {
    ENV: {
      NEXT_PUBLIC_PLATFORM?: string;
      NEXT_PUBLIC_OTEL_SERVICE_NAME?: string;
      NEXT_PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT?: string;
      NEXT_GRAFANA_FARO_ENDPOINT?: string;
    };
  }
}

if (typeof window !== 'undefined') {
  const collector = getCookie('faroCollectorUrl')?.toString() || '';
  Faro(collector);
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
