// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
"use client";
import { FlagConfig } from "@/utils/types";
import React, { ChangeEvent } from "react";

type FeatureFlagProps = {
  flagConfig: FlagConfig;
  selectedVariant: string;
  handleVariantChange: (event: ChangeEvent<HTMLSelectElement>) => void;
};

const DefaultVariantSelect = ({
  flagConfig,
  selectedVariant,
  handleVariantChange,
}: FeatureFlagProps) => {
  return (
    <select
      value={selectedVariant}
      onChange={handleVariantChange}
      className="rounded-md bg-gray-700 px-3 py-1 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      {Object.keys(flagConfig.variants).map((variant: string) => {
        return (
          <option value={variant} key={variant}>
            {variant}
          </option>
        );
      })}
    </select>
  );
};

export default DefaultVariantSelect;
