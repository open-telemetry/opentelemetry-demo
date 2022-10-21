import type { NextApiRequest, NextApiResponse } from 'next';
import InstrumentationMiddleware from '../../utils/telemetry/InstrumentationMiddleware';
import { Empty } from '../../protos/demo';

type TResponse = string[] | Empty;

const {
  ENV_PLATFORM = '',
  OTEL_SERVICE_NAME = 'frontend',
  PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = '',
} = process.env;

const handler = async ({ method }: NextApiRequest, res: NextApiResponse<TResponse>) => {
  switch (method) {
    case 'GET': {
      return res.status(200).json({
        ENV_PLATFORM,
        OTEL_SERVICE_NAME,
        PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT,
      });
    }

    default: {
      return res.status(405);
    }
  }
};

export default InstrumentationMiddleware(handler);
