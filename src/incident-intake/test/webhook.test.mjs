import { test } from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { DefaultGrafanaWebhookMapper, GrafanaWebhookAdapter } from '../dist/adapters/inbound/grafana-webhook.js';
import { createWebhookServer } from '../dist/adapters/inbound/http-server.js';

const payload = () => ({ alerts: [{
  status: 'firing', fingerprint: 'abc', startsAt: '2026-10-15T10:00:00Z',
  endsAt: '0001-01-01T00:00:00Z',
  labels: { service_name: 'cart', severity: 'warning', environment: 'demo' },
  annotations: { summary: 'Cart latency' },
}] });

test('maps mixed statuses and preserves episode identity without treating groupKey as delivery ID', () => {
  const firing = payload().alerts[0];
  const command = new DefaultGrafanaWebhookMapper('demo').map({
    groupKey: 'not-a-delivery-id',
    alerts: [firing, { ...firing, status: 'resolved', endsAt: '2026-10-15T10:10:00Z' }],
  }, '2026-10-15T10:11:00Z');
  assert.equal(command.deliveryId, null);
  assert.deepEqual(command.alerts[0].affectedService, { service: 'cart', environment: 'demo' });
  assert.equal(command.alerts[0].resolvedAt, null);
  assert.equal(command.alerts[1].resolvedAt, '2026-10-15T10:10:00.000Z');
  assert.deepEqual(command.alerts[0].key, command.alerts[1].key);
});

test('rejects the whole notification if an alert is malformed', () => {
  const mapper = new DefaultGrafanaWebhookMapper('demo');
  assert.throws(() => mapper.map({ alerts: [...payload().alerts, {}] }, new Date().toISOString()));
  assert.throws(() => mapper.map({ alerts: [{ ...payload().alerts[0], labels: { severity: 42 } }] }, new Date().toISOString()));
});

test('HTTP endpoint authenticates, validates and waits for processing', async (t) => {
  let calls = 0;
  let fail = false;
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const adapter = new GrafanaWebhookAdapter({ async execute() {
    calls++;
    if (fail) throw new Error('storage unavailable');
    await gate;
    return { incidents: [] };
  } }, new DefaultGrafanaWebhookMapper('demo'));
  const server = createWebhookServer(adapter, { token: 'test-token' });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => new Promise(resolve => {
    server.close(resolve);
    server.closeAllConnections();
  }));
  const url = `http://127.0.0.1:${server.address().port}/webhooks/grafana`;
  const post = (body, authorized = true) => fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(authorized ? { Authorization: 'Bearer test-token' } : {}) },
    body,
  });
  assert.equal((await post(JSON.stringify(payload()), false)).status, 401);
  assert.equal((await post('{')).status, 400);
  assert.equal((await post(JSON.stringify({ alerts: [] }))).status, 400);
  assert.equal((await post(JSON.stringify({ data: 'x'.repeat(1024 * 1024) }))).status, 413);
  assert.equal(calls, 0);
  let responded = false;
  const pending = post(JSON.stringify(payload())).then(response => { responded = true; return response; });
  while (calls === 0) await new Promise(resolve => setTimeout(resolve, 5));
  assert.equal(responded, false);
  release();
  assert.equal((await pending).status, 200);
  fail = true;
  assert.equal((await post(JSON.stringify(payload()))).status, 500);
});

test('maps the Prometheus deployment environment label without modifying original labels', () => {
  const alert = payload().alerts[0];
  const labels = { service_name: 'cart', deployment_environment_name: 'local' };
  const command = new DefaultGrafanaWebhookMapper('demo').map({
    alerts: [{ ...alert, labels }],
  }, '2026-10-16T07:00:00Z');
  assert.deepEqual(command.alerts[0].affectedService, {
    service: 'cart', environment: 'local',
  });
  assert.deepEqual(command.alerts[0].labels, labels);
});