// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
import {
  CompositePropagator,
  W3CBaggagePropagator,
  W3CTraceContextPropagator,
} from "@opentelemetry/core";
import { WebTracerProvider } from "@opentelemetry/sdk-trace-web";
import {
  BatchSpanProcessor,
  SimpleSpanProcessor,
  ConsoleSpanExporter,
} from "@opentelemetry/sdk-trace-base";
import { registerInstrumentations } from "@opentelemetry/instrumentation";
import { getWebAutoInstrumentations } from "@opentelemetry/auto-instrumentations-web";
import { Resource } from "@opentelemetry/resources";
import {
  ATTR_DEVICE_ID,
  ATTR_OS_NAME,
  ATTR_OS_VERSION,
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_VERSION,
} from "@opentelemetry/semantic-conventions/incubating";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import getLocalhost from "@/utils/Localhost";
import { useEffect, useState } from "react";
import {
  getDeviceId,
  getSystemVersion,
  getVersion,
} from "react-native-device-info";
import { Platform } from "react-native";
import {SessionIdProcessor} from "@/utils/SessionIdProcessor";

const Tracer = async () => {
  // TODO Should add a resource detector for React Native that provides this automatically
  const resource = new Resource({
    [ATTR_SERVICE_NAME]: "reactnativeapp",
    [ATTR_OS_NAME]: Platform.OS,
    [ATTR_OS_VERSION]: getSystemVersion(),
    [ATTR_SERVICE_VERSION]: getVersion(),
    [ATTR_DEVICE_ID]: getDeviceId(),
  });

  // TODO Not obvious that the WebTracerProvider can be used for React Native, might be useful to have a thin
  //  ReactNativeTracerProvider on top of it (or BasicTracerProvider) that makes this clear. Could also add some
  //  protection against browser specific functionality being added to WebTracerProvider that breaks functionality
  //  for React Native.
  //  Alternatively could offer a TracerProvider that exposed a JS interface on top of the OTEL Android and Swift SDKS,
  //  giving developers the option of collecting telemetry at the native mobile layer
  const provider = new WebTracerProvider({ resource });

  const localhost = await getLocalhost();
  provider.addSpanProcessor(
    new BatchSpanProcessor(
      new OTLPTraceExporter({
        url: `http://${localhost}:${process.env.EXPO_PUBLIC_FRONTEND_PROXY_PORT}/otlp-http/v1/traces`,
      }),
      {
        scheduledDelayMillis: 500,
      },
    ),
  );

  // TODO introduce a React Native session processor package that could be used here, taking into account mobile
  // specific considerations for the session such as putting the app into the background
  provider.addSpanProcessor(new SessionIdProcessor());

  // Helpful for debugging
  provider.addSpanProcessor(new SimpleSpanProcessor(new ConsoleSpanExporter()));

  provider.register({
    propagator: new CompositePropagator({
      propagators: [
        new W3CBaggagePropagator(),
        new W3CTraceContextPropagator(),
      ],
    }),
  });

  registerInstrumentations({
    tracerProvider: provider,
    instrumentations: [
      // TODO Some tiptoeing required here, 'instrumentation-user-interaction' and 'instrumentation-document-load' are
      // not valid for React Native. For 'instrumentation-fetch' propagateTraceHeaderCorsUrls is required to make it
      // work in the context of a mobile app even though we are not making CORS requests. `clearTimingResources` must
      // be turned off to avoid using the web-only Performance API
      // Overall wrapping or forking these and providing a React Native specific auto instrumentation will ease
      // integration and make it less error-prone
      getWebAutoInstrumentations({
        "@opentelemetry/instrumentation-user-interaction": { enabled: false },
        "@opentelemetry/instrumentation-document-load": { enabled: false },
        "@opentelemetry/instrumentation-fetch": {
          propagateTraceHeaderCorsUrls: /.*/,
          clearTimingResources: false,
        },
      }),
    ],
  });
};

export interface TracerResult {
  loaded: boolean;
}

// TODO providing a wrapper similar to this that uses hooks over the full JS OTEL API would be nice to have for both
// React Native and React development
export const useTracer = (): TracerResult => {
  const [loaded, setLoaded] = useState<boolean>(false);

  useEffect(() => {
    if (!loaded) {
      Tracer()
        .catch(() => console.warn("failed to setup tracer"))
        .finally(() => setLoaded(true));
    }
  }, [loaded]);

  return {
    loaded,
  };
};
