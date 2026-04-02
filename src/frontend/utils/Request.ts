// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

interface IRequestParams {
  url: string;
  body?: object;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  queryParams?: Record<string, any>;
  headers?: Record<string, string>;
}

const request = async <T>({
  url = '',
  method = 'GET',
  body,
  queryParams = {},
  headers = {
    'content-type': 'application/json',
  },
}: IRequestParams): Promise<T> => {
  const queryString = new URLSearchParams(queryParams).toString();
  const requestUrl = queryString ? `${url}?${queryString}` : url;
  const response = await fetch(requestUrl, {
    method,
    body: body ? JSON.stringify(body) : undefined,
    headers,
  });

  const responseText = await response.text();
  const contentType = response.headers.get('content-type') || '';

  if (!response.ok) {
    throw new Error(responseText || `Request to ${requestUrl} failed with status ${response.status}`);
  }

  if (!responseText) return undefined as unknown as T;

  if (contentType.includes('application/json')) {
    return JSON.parse(responseText) as T;
  }

  return responseText as T;
};

export default request;
