// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const file_name = searchParams.get("file_name") || "demo.flagd.json";

  try {
    const filePath = path.join(process.cwd(), "data", file_name);
    const fileContents = fs.readFileSync(filePath, "utf8");
    const data = JSON.parse(fileContents);
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error reading file:", error);
    return NextResponse.json({ error: "Failed to read file" }, { status: 500 });
  }
}
