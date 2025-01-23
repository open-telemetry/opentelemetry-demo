// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
"use client";
import React, { RefObject } from "react";
import { FlagConfig } from "@/utils/types";

type FileEditorProps = {
  flagConfig: FlagConfig;
  textAreaRef: RefObject<HTMLTextAreaElement>;
  handleTextAreaChange: () => void;
};

function FileEditor({
  flagConfig,
  textAreaRef,
  handleTextAreaChange,
}: FileEditorProps) {
  return (
    <textarea
      className="mb-4 h-48 w-full bg-gray-700 p-3 text-sm text-gray-300 focus:border-blue-500 focus:outline-none sm:h-64 md:h-80 lg:h-96 xl:h-[32rem] 2xl:h-[48rem]"
      cols={200}
      ref={textAreaRef}
      defaultValue={JSON.stringify(flagConfig, null, 2)}
      onChange={handleTextAreaChange}
    />
  );
}

export default FileEditor;
