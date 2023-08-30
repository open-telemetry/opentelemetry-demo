// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Document, { DocumentContext, Html, Head, Main, NextScript } from 'next/document';
import { ServerStyleSheet } from 'styled-components';
import Script from 'next/script'

const { ENV_PLATFORM, WEB_OTEL_SERVICE_NAME, PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT } = process.env;
const { INSTANA_EUM_URL, INSTANA_EUM_KEY } = process.env;

const envString = `
window.ENV = {
  NEXT_PUBLIC_PLATFORM: '${ENV_PLATFORM}',
  NEXT_PUBLIC_OTEL_SERVICE_NAME: '${WEB_OTEL_SERVICE_NAME}',
  NEXT_PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: '${PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT}',
  INSTANA_EUM_URL: '${INSTANA_EUM_URL}',
  INSTANA_EUM_KEY: '${INSTANA_EUM_KEY}',
};
`;

export default class MyDocument extends Document<{ envString: string, traceId: string }> {
  static async getInitialProps(ctx: DocumentContext) {
    const sheet = new ServerStyleSheet();
    const originalRenderPage = ctx.renderPage;

    try {
      ctx.renderPage = () =>
        originalRenderPage({
          enhanceApp: App => props => sheet.collectStyles(<App {...props} />),
        });

      const initialProps = await Document.getInitialProps(ctx);
      const traceId = ctx.req?.headers['x-instana-t'] || ''
      return {
        ...initialProps,
        styles: [initialProps.styles, sheet.getStyleElement()],
        envString,
	traceId,
      };
    } finally {
      sheet.seal();
    }
  }

  render() {
    return (
      <Html>
        <Head>
          <link rel="preconnect" href="https://fonts.googleapis.com" />
          <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
          <link
            href="https://fonts.googleapis.com/css2?family=Open+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,300;1,400;1,500;1,600;1,700;1,800&display=swap"
            rel="stylesheet"
          />
          <title>OTel demo</title>
	  <Script id="instana-eum" strategy="beforeInteractive">{`
	  (function(s,t,a,n){s[t]||(s[t]=a,n=s[a]=function(){n.q.push(arguments)},
				    n.q=[],n.v=2,n.l=1*new Date)})(window,"InstanaEumObject","ineum");

	  ineum('reportingUrl', '${INSTANA_EUM_URL}');
	  ineum('key', '${INSTANA_EUM_KEY}');
	  ineum('trackSessions');
	  ineum('traceId', '${this.props.traceId}');
	  `}</Script>
	  <Script strategy="beforeInteractive" defer crossOrigin="anonymous" src={INSTANA_EUM_URL+"/eum.min.js"} />
        </Head>
        <body>
          <Main />
          <script dangerouslySetInnerHTML={{ __html: this.props.envString }}></script>
          <NextScript />
        </body>
      </Html>
    );
  }
}
