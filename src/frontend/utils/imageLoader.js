// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
export default function imageLoader({ src, width, quality }) {
  // Keep image URLs origin-relative so server-rendered and hydrated markup match.
  // The frontend proxy still routes image requests to image-provider in compose.
  return `${src}?w=${width}&q=${quality || 75}`;
}
