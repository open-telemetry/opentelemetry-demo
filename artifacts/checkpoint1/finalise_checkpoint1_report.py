"""Apply the recorded operator review to this run's new report artifact only."""

import json
from pathlib import Path
from checkpoint1_observe import HOME, now, save, verify


run = 'eyes-20261023T094107764041Z'
path = HOME / 'checkpoint1_incident_report.md'
text = path.read_text(encoding='utf-8')
if run not in text:
    raise SystemExit('This review is specific to the captured scoped run; do not apply it to another run.')
start = text.index('```json', text.index('## LLM provider and model'))
end = text.index('```', start + len('```json')) + 3
reviewed = '''The local model helped organise the returned failures. Its output was reviewed against the actual responses. The accepted synthesis is:

- No containers matched this demo's Compose project in Ubuntu Docker, and no matching lifecycle events were returned in the requested window ([E001](runs/eyes-20261023T094107764041Z/E001.json), [E002](runs/eyes-20261023T094107764041Z/E002.json)). These facts establish neither application health nor deployment history.
- Prometheus returned connection refusals for the three requested queries; there are **no metric samples or measured anomalies** in this run ([E003](runs/eyes-20261023T094107764041Z/E003.json), [E004](runs/eyes-20261023T094107764041Z/E004.json), [E005](runs/eyes-20261023T094107764041Z/E005.json)).
- Jaeger service and trace requests also returned connection refusals; there are **no retrieved traces or error spans** ([E006](runs/eyes-20261023T094107764041Z/E006.json), [E007](runs/eyes-20261023T094107764041Z/E007.json)). The model had grouped these under metrics; that categorisation is corrected here.
- No OpenSearch port was discoverable because there was no matching demo container. No application/system log lines were retrieved ([E008](runs/eyes-20261023T094107764041Z/E008.json)). This is not evidence of a specific application/configuration fault.
- No practice incident was executed ([E009](runs/eyes-20261023T094107764041Z/E009.json)). Inventory/events commands and local inference did succeed; the model's phrase “no successful executions” must not be read as denying those successful read operations.

**Interpretation:** the required demo observability endpoints were unavailable from the collector during this attempt. Their underlying cause is not established. No practice-incident root cause, service recovery, or deployment/configuration change is inferred.

The original scoped model output remains in [E011](runs/eyes-20261023T094107764041Z/E011.json); the review is recorded in [operator_review.json](runs/eyes-20261023T094107764041Z/operator_review.json). An earlier run's invented running-MinIO claim was separately rejected and is excluded from accepted findings.'''
text = text[:start] + reviewed + text[end:]
text = text.replace('The model output below is an interpretation requiring operator review, not additional telemetry.',
                    'The model proposal is retained as inference evidence; only the reviewed synthesis below is accepted for this report.')
text = text.replace('Request completed; inspect the saved result before inferring health.',
                    'Read operation completed; this does not establish application health.')
text += '\n## Acceptance status\n\n**Completed:** source/capability reconnaissance, real local inference, referenced environment observations, external route controls, one-page architecture, and preservation checks.\n\n**Incomplete:** real practice execution, incident log/metric/trace collection, deployment/change correlation, autonomous observability in the existing shopping agent, cloud inference, and real cross-provider fallback. This is not a passed Eyes checkpoint.\n'
path.write_text(text, encoding='utf-8')
save(HOME / 'runs' / run / 'operator_review.json', {
    'reviewed_utc': now(), 'accepted_with_corrections': True,
    'corrections': ['E006/E007 are traces, not metric requests',
                    'No successful practice execution does not mean no successful read operations',
                    'No specific application/configuration root cause is established'],
    'supported_findings': {'E001': 'No matching demo containers', 'E002': 'No matching lifecycle events',
                           'E003-E005': 'Prometheus connection refused',
                           'E006-E007': 'Jaeger connection refused',
                           'E008': 'No OpenSearch port discovered', 'E009': 'Practice not executed'},
    'model_output_remains_untrusted_as_telemetry': True})
print('Final report reviewed against saved observations; incomplete acceptance is explicit.')
raise SystemExit(0 if verify() else 2)
