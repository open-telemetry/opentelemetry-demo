import { TracingInstrumentation } from '@grafana/faro-web-tracing';
import { getWebInstrumentations, initializeFaro } from '@grafana/faro-web-sdk';

const { NEXT_PUBLIC_OTEL_SERVICE_NAME = '', NEXT_GRAFANA_FARO_ENDPOINT = '' } =
  typeof window !== 'undefined' ? window.ENV : {};

const Faro = async (collectorString: string) => {
  initializeFaro({
    url: NEXT_GRAFANA_FARO_ENDPOINT || collectorString,

    // Mandatory, the identification label(s) of your application
    app: {
      name: NEXT_PUBLIC_OTEL_SERVICE_NAME,
      version: '1.0.0', // Optional, but recommended
    },

    instrumentations: [
      // Mandatory, overwriting the instrumentations array would cause the default instrumentations to be omitted
      ...getWebInstrumentations(),

      // Mandatory, initialization of the tracing package
      new TracingInstrumentation(),
    ],
  });
};

export default Faro;
