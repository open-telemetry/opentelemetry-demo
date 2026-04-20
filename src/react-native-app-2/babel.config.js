// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
  };
};
