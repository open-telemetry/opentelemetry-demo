// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

/*
 * Images are served through the same frontend-proxy origin as the application.
 * Return the same relative URL during SSR and client rendering so the generated
 * image attributes remain stable during hydration.
 */
export default function imageLoader({ src, width, quality }) {
  const normalizedSrc = `/${src.replace(/^\/+/, '')}`;
  return `${normalizedSrc}?w=${width}&q=${quality || 75}`;
}
