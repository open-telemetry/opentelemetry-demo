// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
"use client";
import React, { ChangeEvent, useCallback, useEffect } from "react";
import { useState } from "react";
import DefaultVariantSelect from "./DefaultVariantSelect";
import { FlagConfig } from "@/utils/types";

type FeatureFlagProps = {
  flagId: string;
  flagConfig: FlagConfig;
  updateFlagData: (fladId: string, selectedVariant: string) => void;
};

function FeatureFlag({ flagId, flagConfig, updateFlagData }: FeatureFlagProps) {
  const [selectedVariant, setSelectedVariant] = useState<string>("");

  useEffect(() => {
    setSelectedVariant(flagConfig.defaultVariant);
  }, [flagConfig.defaultVariant]);

  const handleVariantChange = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      setSelectedVariant(event.target.value);
      updateFlagData(flagId, event.target.value);
    },
    [flagId, updateFlagData],
  );

  return (
    <div className="mb-4 flex flex-auto flex-col justify-between rounded-md bg-gray-800 p-6 text-gray-300 shadow-md">
      <div>
        <div className="mb-4 text-lg font-semibold">{`${flagId}`}</div>
        <p className="mb-4 text-sm">{`${flagConfig.description}`}</p>
      </div>
      <div>
        <div className="flex items-center justify-between">
          <DefaultVariantSelect
            flagConfig={flagConfig}
            selectedVariant={selectedVariant}
            handleVariantChange={handleVariantChange}
          />
        </div>
      </div>
    </div>
  );
}

export default FeatureFlag;
