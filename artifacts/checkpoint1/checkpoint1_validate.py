"""Targeted observer checks. Simulated route outcomes are not live provider evidence."""

import ast
import copy
import json
import os
from pathlib import Path
import tomllib
from unittest.mock import patch
from checkpoint1_observe import HOME, Observer, ROUTES, local_url, sanitise, save, verify


config = tomllib.loads((HOME / 'checkpoint1_observe.toml').read_text())
results = []


def check(name, passed):
    results.append({'check': name, 'passed': bool(passed)})
    if not passed:
        raise AssertionError(name)


for route, expected in ROUTES.items():
    observer = object.__new__(Observer)
    observer.config = copy.deepcopy(config)
    observer.config['route'] = route
    observer.events = []
    observer.record = lambda *args, **kwargs: None
    calls = []

    def simulated(slot, messages):
        calls.append(slot)
        if len(expected) == 2 and len(calls) == 1:
            raise ValueError('Simulated primary failure, no network request')
        return {'provider': 'SIMULATED', 'model': 'SIMULATED', 'slot': slot,
                'text': json.dumps({'executive_summary': 'Routing test only', 'observations': []})}

    observer.model_call = simulated
    result = observer.summarise()
    check(route + ' selects documented order after simulated primary failure', calls == expected)
    check(route + ' records selected profile', result['slot'] == expected[-1])

observer.config['route'] = 'local-only'
observer.model_call = lambda slot, messages: {
    'provider': 'SIMULATED', 'model': 'SIMULATED',
    'text': json.dumps({'executive_summary': 'Test only', 'observations': [
        {'text': 'Unsupported test claim', 'evidence_ids': ['E999']}]})}
check('invented evidence ID rejected', observer.summarise()['summary'] is None)

observer.config = copy.deepcopy(config)
try:
    observer.model_call = Observer.model_call.__get__(observer)
    observer.model_call('cloud', [])
    check('disabled cloud rejected without network request', False)
except ValueError as exc:
    check('disabled cloud rejected without network request', 'disabled' in str(exc))

observer.config['cloud']['enabled'] = True
observer.config['cloud']['endpoint'] = 'https://example.invalid/v1'
observer.config['cloud']['model'] = 'operator-model'
with patch.dict(os.environ, {'CHECKPOINT1_CLOUD_API_KEY': ''}):
    try:
        observer.model_call('cloud', [])
        check('missing cloud key fails closed', False)
    except ValueError as exc:
        check('missing cloud key fails closed', 'credential' in str(exc))

with patch.dict(os.environ, {'CHECKPOINT1_CLOUD_API_KEY': 'fixture-test-credential'}):
    check('configured secret value is redacted',
          'fixture-test-credential' not in sanitise('key fixture-test-credential'))
check('public telemetry endpoint not permitted', not local_url('https://example.com'))
for filename in ('checkpoint1_observe.py', 'checkpoint1_recon.py', 'render_checkpoint1_architecture.py'):
    ast.parse((HOME / filename).read_text(encoding='utf-8'))
check('new external scripts parse without importing application source', True)
check('all 664 original files still match', verify())
save(HOME / 'routing_validation.json', {
    'type': 'Unit/negative-path validation; simulated model outcomes, not cloud execution',
    'cloud_network_requests': 0, 'checks': results,
    'passed': all(item['passed'] for item in results)})
print(json.dumps({'passed_checks': len(results), 'cloud_network_requests': 0}, indent=2))
