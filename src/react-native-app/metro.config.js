// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Learn more https://docs.expo.io/guides/customizing-metro
/* eslint-env node */

const { getDefaultConfig } = require("expo/metro-config");

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// Needed so that we can make use of the alternative @opentelemetry/semantic-conventions/incubating export
// See: https://reactnative.dev/blog/2023/06/21/package-exports-support
config.resolver.unstable_enablePackageExports = true;

module.exports = config;
