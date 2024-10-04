// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
import React from "react";

const Spinner = () => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900 bg-opacity-50">
      <div className="h-16 w-16 animate-spin rounded-full border-b-2 border-t-2 border-blue-500"></div>
    </div>
  );
};

export default Spinner;
