// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
/*
  * We connect to image-provider through the envoy proxy, straight from the browser.
  * Using relative URLs ensures images load correctly in all environments:
  * - Local development
  * - Kubernetes behind load balancer
  * - Any reverse proxy setup
  * The browser automatically resolves relative URLs using the current page's origin.
  */

export default function imageLoader({ src, width, quality }) {
  // We pass down the optimisation request to the image-provider service here, without this, nextJs would try to use internal optimiser which is not working with the external image-provider.
  // Strip leading slash from src to prevent double slashes in URL
  const cleanSrc = src.startsWith('/') ? src.slice(1) : src;
  // Use relative URL - browser will resolve using current page's origin
  // This works in all environments: localhost, K8s load balancer, reverse proxies, etc.
  return `/${cleanSrc}?w=${width}&q=${quality || 75}`
}
