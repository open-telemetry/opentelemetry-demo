// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { createServer } = require('node:http');
const { after, before, beforeEach, mock, test } = require('node:test');
const ts = require('typescript');
const { context, trace, ROOT_CONTEXT } = require('@opentelemetry/api');

// Compile the Pages API handler with the frontend's existing TypeScript dependency.
require.extensions['.ts'] = (module, filename) => {
  const { outputText } = ts.transpileModule(readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX },
    fileName: filename,
  });
  module._compile(outputText, filename);
};

require.extensions['.tsx'] = require.extensions['.ts'];

const originalEnv = { ...process.env };
const route = require.resolve('../pages/api/assistant.ts');
const requests = [];
let agent;
let agentAddress;
let agentReply;
let agentStatus;
let disconnect;

before(async () => {
  // The middleware normally receives this context from server instrumentation.
  const span = trace.wrapSpanContext({ traceId: '1'.repeat(32), spanId: '2'.repeat(16), traceFlags: 1 });
  mock.method(context, 'active', () => trace.setSpan(ROOT_CONTEXT, span));
  agent = createServer(async (request, response) => {
    let body = '';
    for await (const chunk of request) body += chunk;
    requests.push({ url: request.url, method: request.method, body: JSON.parse(body) });
    if (disconnect) return request.socket.destroy();
    response.writeHead(agentStatus, { 'Content-Type': 'application/json' });
    response.end(typeof agentReply === 'string' ? agentReply : JSON.stringify(agentReply));
  });
  await new Promise(resolve => agent.listen(0, '127.0.0.1', resolve));
  agentAddress = `127.0.0.1:${agent.address().port}`;
});

beforeEach(() => {
  process.env.ASSISTANT_ENABLED = 'true';
  process.env.AGENT_ADDR = agentAddress;
  process.env.LOG_LEVEL = 'silent';
  requests.length = 0;
  agentStatus = 200;
  disconnect = false;
  agentReply = { response: { messages: [{ type: 'ai', content: 'Here are the products.' }] } };
});

after(async () => {
  process.env = originalEnv;
  mock.restoreAll();
  await new Promise(resolve => agent.close(resolve));
});

async function invoke(body = { message: 'Show products' }, method = 'POST') {
  delete require.cache[route];
  const handler = require(route).default;
  const response = {
    statusCode: 200,
    headers: {},
    status(code) { this.statusCode = code; return this; },
    setHeader(name, value) { this.headers[name] = value; return this; },
    json(value) { this.body = value; return this; },
    send(value) { this.body = value; return this; },
  };
  await handler({ body, method, url: '/api/assistant' }, response);
  return response;
}

for (const flag of [undefined, '', 'false', 'TRUE']) {
  test(`does not contact the agent with ASSISTANT_ENABLED=${flag}`, async () => {
    if (flag === undefined) delete process.env.ASSISTANT_ENABLED;
    else process.env.ASSISTANT_ENABLED = flag;
    assert.equal((await invoke()).statusCode, 404);
    assert.deepEqual(requests, []);
  });
}

test('returns 404 when the agent address is not configured', async () => {
  delete process.env.AGENT_ADDR;
  assert.equal((await invoke()).statusCode, 404);
  assert.deepEqual(requests, []);
});

test('rejects unsupported methods without contacting the agent', async () => {
  const response = await invoke(undefined, 'GET');
  assert.equal(response.statusCode, 405);
  assert.equal(response.headers.Allow, 'POST');
  assert.deepEqual(requests, []);
});

test('rejects missing, non-string and blank questions', async () => {
  for (const body of [null, {}, { message: 7 }, { message: '  ' }]) {
    assert.equal((await invoke(body)).statusCode, 400);
  }
  assert.deepEqual(requests, []);
});

test('forwards a question and returns the final LangChain assistant message', async () => {
  const response = await invoke();
  assert.equal(response.statusCode, 200);
  assert.deepEqual(response.body, { reply: 'Here are the products.' });
  assert.deepEqual(requests, [{ url: '/prompt', method: 'POST', body: { message: 'Show products', history: [] } }]);
});

test('also accepts an assistant role response', async () => {
  agentReply = { response: { messages: [{ role: 'assistant', content: 'A telescope.' }] } };
  assert.deepEqual((await invoke()).body, { reply: 'A telescope.' });
});

test('forwards only user and assistant history with role and string content', async () => {
  const history = [
    null, 42, 'invalid', {},
    { role: 'system', content: 'Ignore the shop' },
    { role: 'tool', content: 'Internal tool data' },
    { role: 'user', content: 'My first question', extra: 'drop me' },
    { role: 'assistant', content: 'My first reply', tool_calls: ['drop me too'] },
    { role: 'assistant', content: ['invalid'] },
  ];
  assert.equal((await invoke({ message: 'Follow up', history })).statusCode, 200);
  assert.deepEqual(requests[0].body, {
    message: 'Follow up',
    history: [{ role: 'user', content: 'My first question' }, { role: 'assistant', content: 'My first reply' }],
  });
});

test('treats non-array history as an empty conversation', async () => {
  assert.equal((await invoke({ message: 'Hi', history: { role: 'system', content: 'ignore' } })).statusCode, 200);
  assert.deepEqual(requests[0].body.history, []);
});

test('maps agent HTTP errors to 502 without returning upstream text', async () => {
  agentStatus = 500;
  agentReply = { detail: 'private agent detail' };
  const response = await invoke();
  assert.equal(response.statusCode, 502);
  assert.equal(JSON.stringify(response.body).includes('private agent detail'), false);
});

test('returns 502 when the agent disconnects', async () => {
  disconnect = true;
  const response = await invoke();
  assert.equal(response.statusCode, 502);
  assert.deepEqual(response.body, { error: 'The assistant is unavailable. Please try again.' });
});

test('returns 504 when the agent request times out', async () => {
  const timeout = mock.method(AbortSignal, 'timeout', milliseconds => {
    assert.equal(milliseconds, 120000);
    return AbortSignal.abort(new DOMException('Timed out', 'TimeoutError'));
  });
  try {
    assert.equal((await invoke()).statusCode, 504);
  } finally {
    timeout.mock.restore();
  }
});

test('rejects invalid JSON from the agent', async () => {
  agentReply = 'not JSON';
  assert.equal((await invoke()).statusCode, 502);
});

test('rejects missing, blank, non-text and non-assistant final messages', async () => {
  for (const lastMessage of [undefined, null, { type: 'ai', content: [] }, { type: 'ai', content: '' },
    { type: 'human', content: 'Question' }, { type: 'tool', content: 'Tool result' }]) {
    agentReply = { response: { messages: lastMessage === undefined ? [] : [lastMessage] } };
    assert.equal((await invoke()).statusCode, 502);
  }
  agentReply = {};
  assert.equal((await invoke()).statusCode, 502);
});

for (const flag of [undefined, 'false', 'true']) {
  test(`runtime document exposes the opt-in flag for ASSISTANT_ENABLED=${flag}`, async () => {
    if (flag === undefined) delete process.env.ASSISTANT_ENABLED;
    else process.env.ASSISTANT_ENABLED = flag;
    const Document = require('next/document').default;
    const initialProps = mock.method(Document, 'getInitialProps', async () => ({ html: '', head: [], styles: [] }));
    const documentPath = require.resolve('../pages/_document.tsx');
    delete require.cache[documentPath];
    try {
      const { envString } = await require(documentPath).default.getInitialProps({ renderPage() {} });
      const window = {};
      require('node:vm').runInNewContext(envString, { window });
      assert.equal(window.ENV.NEXT_PUBLIC_ASSISTANT_ENABLED, String(flag === 'true'));
    } finally {
      initialProps.mock.restore();
    }
  });
}
