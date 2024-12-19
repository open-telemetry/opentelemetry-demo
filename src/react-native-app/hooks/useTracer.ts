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
} from "@opentelemetry/sdk-trace-base";
import { XMLHttpRequestInstrumentation } from "@opentelemetry/instrumentation-xml-http-request";
import { FetchInstrumentation } from "@opentelemetry/instrumentation-fetch";
import { registerInstrumentations } from "@opentelemetry/instrumentation";
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
import { SessionIdProcessor } from "@/utils/SessionIdProcessor";

const Tracer = async () => {
  const localhost = await getLocalhost();

  // TODO Should add a resource detector for React Native that provides this automatically
  const resource = new Resource({
    [ATTR_SERVICE_NAME]: "react-native-app",
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
  const provider = new WebTracerProvider({
    resource,
    spanProcessors: [
      new BatchSpanProcessor(
        new OTLPTraceExporter({
          url: `http://${localhost}:${process.env.EXPO_PUBLIC_FRONTEND_PROXY_PORT}/otlp-http/v1/traces`,
        }),
        {
          scheduledDelayMillis: 500,
        },
      ),

      // TODO introduce a React Native session processor package that could be used here, taking into account mobile
      // specific considerations for the session such as putting the app into the background
      new SessionIdProcessor(),
    ],
  });

  provider.register({
    propagator: new CompositePropagator({
      propagators: [
        new W3CBaggagePropagator(),
        new W3CTraceContextPropagator(),
      ],
    }),
  });

  registerInstrumentations({
    instrumentations: [
      // TODO Some tiptoeing required here, propagateTraceHeaderCorsUrls is required to make the instrumentation
      // work in the context of a mobile app even though we are not making CORS requests. `clearTimingResources` must
      // be turned off to avoid using the web-only Performance API
      // Overall wrapping or forking this and providing a React Native specific auto instrumentation will ease
      // integration and make it less error-prone
      new FetchInstrumentation({
        propagateTraceHeaderCorsUrls: /.*/,
        clearTimingResources: false,
      }),

      // The React Native implementation of fetch is simply a polyfill on top of XMLHttpRequest:
      // https://github.com/facebook/react-native/blob/7ccc5934d0f341f9bc8157f18913a7b340f5db2d/packages/react-native/Libraries/Network/fetch.js#L17
      // Because of this when making requests using `fetch` there will an additional span created for the underlying
      // request made with XMLHttpRequest. Since in this demo calls to /api/ are made using fetch, turn off
      // instrumentation for that path to avoid the extra spans.
      new XMLHttpRequestInstrumentation({
        ignoreUrls: [/\/api\/.*/],
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
