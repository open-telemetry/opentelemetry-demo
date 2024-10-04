// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
import { registerOTel } from "@vercel/otel";

export function register() {
  registerOTel({ serviceName: "flagd-ui" });
}
