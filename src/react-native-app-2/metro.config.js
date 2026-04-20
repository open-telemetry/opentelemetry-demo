// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Learn more https://docs.expo.io/guides/customizing-metro
/* eslint-env node */

const { getDefaultConfig } = require("expo/metro-config");

// Expo SDK 54 enables `resolver.unstable_enablePackageExports` by default, which
// is required for `@opentelemetry/semantic-conventions/incubating` to resolve.
// See: https://reactnative.dev/blog/2023/06/21/package-exports-support

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

module.exports = config;
