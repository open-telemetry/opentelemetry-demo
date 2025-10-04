// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Copied with modification from src/frontend/utils/Request.ts
 */
import getLocalhost from "@/utils/Localhost";

interface IRequestParams {
  url: string;
  body?: object;
  method?: "GET" | "POST" | "PUT" | "DELETE";
  queryParams?: Record<string, any>;
  headers?: Record<string, string>;
}

const request = async <T>({
  url = "",
  method = "GET",
  body,
  queryParams = {},
  headers = {
    "content-type": "application/json",
  },
}: IRequestParams): Promise<T> => {
  const localhost = await getLocalhost();
  const API_URL = `http://${localhost}:${process.env.EXPO_PUBLIC_FRONTEND_PROXY_PORT}`;
  const requestURL = `${API_URL}${url}?${new URLSearchParams(queryParams).toString()}`;
  const requestBody = body ? JSON.stringify(body) : undefined;
  const response = await fetch(requestURL, {
    method,
    body: requestBody,
    headers,
  });

  const responseText = await response.text();

  if (!!responseText) return JSON.parse(responseText);

  return undefined as unknown as T;
};

export default request;
