// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
"use client";
import React, { useEffect, useState } from "react";
import FeatureFlag from "./FeatureFlag";
import { ConfigFile, FlagConfig } from "@/utils/types";
import { useLoading } from "../Layout";

const BasicView = () => {
  const [flagData, setFlagData] = useState<ConfigFile | null>(null);
  const [originalFlagData, setOriginalFlagData] = useState<ConfigFile | null>(
    null,
  );
  const [reloadData, setReloadData] = useState(false);

  const { setIsLoading } = useLoading();

  useEffect(() => {
    const readFile = async () => {
      try {
        const response = await fetch("/feature/api/read-file", {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        });
        const data = await response.json();
        setFlagData(data);
        setOriginalFlagData(data);
      } catch (err: unknown) {
        window.alert(err);
        console.error(err);
      }
    };
    readFile();

    if (reloadData) {
      setReloadData(false);
    }
  }, [reloadData]);

  const updateFlagData = (flagId: string, selectedVariant: string) => {
    setFlagData((prevFlagData) => {
      if (!prevFlagData) return prevFlagData;

      return {
        ...prevFlagData,
        flags: {
          ...prevFlagData.flags,
          [flagId]: {
            ...prevFlagData.flags[flagId],
            defaultVariant: selectedVariant,
          },
        },
      };
    });
  };

  const save = async () => {
    try {
      setIsLoading(true);
      await fetch("/feature/api/write-to-file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: flagData }),
      });
      setIsLoading(false);
      setReloadData(true);
    } catch (err: unknown) {
      window.alert(err);
      console.error(err);
    }
  };

  const flagDataIsSynced =
    JSON.stringify(flagData) === JSON.stringify(originalFlagData);

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8 flex flex-auto items-center gap-2">
        <button
          className="rounded bg-blue-500 px-8 py-4 font-medium text-white transition-colors duration-200 hover:bg-blue-600"
          onClick={save}
        >
          save
        </button>
        {!flagDataIsSynced && <p className="text-red-600">Unsaved changes</p>}
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {flagData &&
          Object.keys(flagData.flags).map((flagId) => {
            const flagConfig: FlagConfig = flagData.flags[flagId];
            return (
              <FeatureFlag
                flagId={flagId}
                key={flagId}
                flagConfig={flagConfig}
                updateFlagData={updateFlagData}
              />
            );
          })}
      </div>
    </div>
  );
};
export default BasicView;
