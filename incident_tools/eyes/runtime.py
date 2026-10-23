"""Operator-selected inference and artifact rendering, with no application mutations."""
import json
import os
from pathlib import Path
import time
import tomllib
from urllib import request, parse

from incident_tools.f02.boundary import NoRedirect, finite


DEFAULTS = {'poll_seconds': 15, 'window_seconds': 300, 'consecutive_breaches': 2,
            'max_age_seconds': 90, 'warmup_seconds': 120, 'min_requests': 10, 'cooldown_seconds': 300,
            'thresholds': {'error_rate': 0.05, 'latency_p95_ms': 1000},
            'max_calls': 12, 'max_seconds': 120, 'per_call_limit': 1, 'evidence_chars': 12000}


def load(file):
    file = Path(file).resolve()
    with file.open('rb') as stream:
        cfg = tomllib.load(stream)
    settings = {**DEFAULTS, **cfg.get('workflow', {})}
    if set(settings) - (set(DEFAULTS) | {'services'}):
        raise ValueError('Unknown workflow option')
    for key, cap in {'poll_seconds': 300, 'window_seconds': 3600, 'consecutive_breaches': 20,
                     'max_age_seconds': 600, 'warmup_seconds': 3600, 'min_requests': 100000,
                     'cooldown_seconds': 86400, 'max_calls': 30, 'max_seconds': 600,
                     'per_call_limit': 50, 'evidence_chars': 24000}.items():
        if type(settings[key]) is not int or not 1 <= settings[key] <= cap:
            raise ValueError('Invalid bound: ' + key)
    if not settings.get('services') or not isinstance(settings['services'], list):
        raise ValueError('Configure monitored services')
    if not settings['thresholds'] or set(settings['thresholds']) - {'error_rate', 'latency_p95_ms'}:
        raise ValueError('Unsupported alert metric')
    for metric, value in settings['thresholds'].items():
        if finite(value) <= 0 or (metric == 'error_rate' and value >= 1):
            raise ValueError('Invalid threshold')
    resolve = lambda name: str((file.parent / cfg[name]).resolve())
    return cfg, settings, resolve('f02_config'), resolve('artifact_dir')


class Router:
    def __init__(self, cfg):
        self.route = cfg['route']
        orders = {'local-only': ['local'], 'cloud-only': ['cloud'], 'local-first': ['local', 'cloud'], 'cloud-first': ['cloud', 'local']}
        if self.route not in orders:
            raise ValueError('Invalid model route')
        self.order, self.cfg, self.last = orders[self.route], cfg, {}
        self.opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
        for slot in self.order:
            item = cfg.get(slot, {})
            if not item.get('enabled', False):
                raise ValueError('Selected provider is not explicitly enabled')
            url = parse.urlsplit(item['endpoint'])
            if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError('Invalid inference endpoint')
            if item['backend'] not in ('ollama', 'openai-compatible') or not item.get('model'):
                raise ValueError('Configure an existing compatible provider and model')
            if slot == 'cloud' and (url.scheme != 'https' or not os.environ.get(item.get('api_key_env', ''))):
                raise ValueError('Cloud requires HTTPS and an environment API key')
            for key, default, cap in [('timeout_seconds', 30, 120), ('retries', 0, 2), ('max_output_tokens', 768, 4096),
                                      ('context_chars', 32000, 64000), ('requests_per_minute', 6, 120)]:
                val = item.setdefault(key, default)
                if type(val) is not int or not (0 if key == 'retries' else 1) <= val <= cap:
                    raise ValueError('Invalid provider limit')
            item.setdefault('temperature', 0.0)
            if not 0 <= finite(item['temperature']) <= 2:
                raise ValueError('Invalid temperature')

    @property
    def public_configuration(self):
        return {'route': self.route, 'providers': {slot: {key: value for key, value in self.cfg[slot].items()
                if key in ('backend', 'model', 'timeout_seconds', 'retries', 'context_chars', 'context_window',
                           'max_output_tokens', 'temperature', 'requests_per_minute', 'num_thread', 'num_gpu')}
                for slot in self.order}}

    def decide(self, messages, remaining):
        deadline = time.monotonic() + remaining
        for slot in self.order:
            cfg = self.cfg[slot]
            if len(json.dumps(messages)) > cfg['context_chars']:
                continue
            for attempt in range(cfg['retries'] + 1):
                delay = max(0, 60 / cfg['requests_per_minute'] - (time.monotonic() - self.last.get(slot, -10000)))
                if deadline - time.monotonic() <= delay:
                    break
                if delay:
                    time.sleep(delay)
                payload = {'model': cfg['model'], 'messages': messages, 'stream': False}
                if cfg['backend'] == 'ollama':
                    route = '/api/chat'
                    payload.update(format='json', options={'temperature': cfg['temperature'], 'num_predict': cfg['max_output_tokens'],
                                                          'num_ctx': cfg.get('context_window', 8192), 'num_thread': cfg.get('num_thread', 4),
                                                          'num_gpu': cfg.get('num_gpu', 0)}, keep_alive='0s')
                else:
                    route = '/chat/completions'
                    payload.update(max_tokens=cfg['max_output_tokens'], temperature=cfg['temperature'])
                headers = {'Content-Type': 'application/json'}
                if cfg.get('api_key_env'):
                    token = os.environ.get(cfg['api_key_env'])
                    if not token:
                        break
                    headers['Authorization'] = 'Bearer ' + token
                req = request.Request(cfg['endpoint'].rstrip('/') + route, data=json.dumps(payload).encode(), headers=headers)
                self.last[slot] = time.monotonic()
                try:
                    timeout = min(cfg['timeout_seconds'], deadline - time.monotonic())
                    if timeout <= 0:
                        break
                    with self.opener.open(req, timeout=timeout) as response:
                        raw = response.read(262145)
                    if len(raw) > 262144:
                        raise ValueError('Oversized inference response')
                    body = json.loads(raw, parse_constant=finite)
                    content = body['message']['content'] if cfg['backend'] == 'ollama' else body['choices'][0]['message']['content']
                    return json.loads(content, parse_constant=finite), {'slot': slot, 'backend': cfg['backend'], 'model': cfg['model'], 'route': self.route}
                except Exception:
                    continue
        raise RuntimeError('No configured provider returned a valid decision within the request budget')


def export(run, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    def write(name, content):
        (directory / name).write_text(content, encoding='utf-8')
    write('checkpoint1_execution_log.json', json.dumps(run, indent=2, allow_nan=False))
    incident = run['incident']
    lines = ['# Eyes incident symptom report', '', 'Origin: ' + run['origin'],
             'Incident: ' + incident['id'], 'Service: ' + incident['service'],
             'Window: ' + json.dumps(incident['window']), '', '## Executive summary',
             'An automatically detected metric breach initiated this observation workflow. Root cause is not established.',
             '', '## Observed alert facts']
    for alert in incident['alerts']:
        lines.append('- ' + json.dumps(alert))
    lines.extend(['', '## Telemetry and timeline'])
    for entry in run['evidence']:
        lines.append('- ' + entry['collected_at'] + ' — ' + entry.get('tool', 'tool') + ': ' + entry['status'] + ' [' + entry['evidence_id'] + ']')
        lines.append('~~~json\n' + json.dumps(entry, indent=2) + '\n~~~')
    lines.extend(['', '## Model interpretations (require operator review)'])
    lines.extend('- ' + claim['text'].replace('\n', ' ') + ' [' + ', '.join(claim['evidence_ids']) + ']' for claim in run['interpretations'])
    lines.extend(['', '## Missing evidence and limitations', *['- ' + str(x) for x in run['limitations']], '',
                  '## Model execution', '~~~json', json.dumps([d['model'] for d in run['decisions']], indent=2), '~~~',
                  'Stop reason: ' + run['stop_reason']])
    write('checkpoint1_incident_report.md', '\n'.join(lines) + '\n')
    write('checkpoint1_execution_log.md', '# Execution record\n\nSee checkpoint1_execution_log.json for ordered model decisions, provider/model identity, tool arguments/results, timestamps and evidence IDs.\n\nOrigin: ' + run['origin'] + '\nStop reason: ' + run['stop_reason'] + '\n')
    write('checkpoint1_llm_configuration.md', '# Model configuration (credentials and connection details omitted)\n\n~~~json\n' + json.dumps(run.get('model_configuration', {}), indent=2) + '\n~~~\nActual provider/model for each step is recorded in the execution log.\n')
    write('checkpoint1_architecture.svg', architecture())


def architecture():
    boxes = [ (20,60,'Existing demo + load generator'), (20,150,'Collector → Prometheus / Jaeger / OpenSearch'),
              (20,240,'F02 bounded read tools + Docker state/events'),
              (570,60,'F01 poller + freshness check'), (570,150,'SQLite incidents / dedup / queue'),
              (570,240,'F03 single diagnostic investigator'), (20,350,'Local Ollama — operator configured'),
              (570,350,'Cloud compatible API — optional / configured'),
              (280,450,'Operator-selected model route / fallback'), (280,550,'Evidence JSON + symptom report + this SVG')]
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="730" viewBox="0 0 1100 730">',
             '<rect width="1100" height="730" fill="white"/>',
             '<style>text{font:14px sans-serif}rect{stroke:#174466;fill:#eef6fc}path{stroke:#174466;fill:none;stroke-width:2}</style>',
             '<text x="20" y="30">Eyes architecture — integrations require operator configuration; live demonstration pending</text>']
    for x,y,text in boxes:
        parts.extend([f'<rect x="{x}" y="{y}" width="490" height="50" rx="8"/>', f'<text x="{x+12}" y="{y+30}">{text}</text>'])
    parts.extend(['<path d="M265 110V150 M265 200V240 M510 265H570 M815 110V150 M815 200V240 M265 290V350 M815 290V350 M265 400V475H280 M815 400V475H770 M525 500V550"/>',
                  '<text x="20" y="655">Deployment audit feed: optional, unavailable unless supplied. Logs/traces never expose flag files.</text>',
                  '<text x="20" y="690">Proposed later: diagnosis, Action API, human approval, kill switch, recovery verification.</text>', '</svg>'])
    return '\n'.join(parts)
