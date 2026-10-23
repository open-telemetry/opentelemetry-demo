"""Record safe capability metadata without disclosing configured credentials."""

import importlib.util
import json
import os
from pathlib import Path
import urllib.request
from checkpoint1_observe import HOME, ROOT, now, save, sanitise


tracked_names = ('API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY',
                 'AZURE_OPENAI_API_KEY', 'CHECKPOINT1_CLOUD_API_KEY')
presence = {'process_environment': {name: bool(os.environ.get(name)) for name in tracked_names}}
safe = {}
for filename in ('.env', '.env.override'):
    values = {}
    for line in (ROOT / filename).read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            key, value = stripped.split('=', 1)
            values[key.strip()] = value.strip().strip(chr(34)).strip(chr(39))
    presence[filename] = {name: bool(values.get(name)) and values[name] not in
                         ('sk-dummy', 'your-api-key', '${API_KEY}') for name in tracked_names}
    safe[filename] = {name: sanitise(values.get(name, '<unset>')) for name in
                     ('LLM_MODEL', 'USE_VCR', 'MCP_ENABLED', 'GRAPH_RECURSION_LIMIT')}
    safe[filename]['LLM_BASE_URL_configured'] = bool(values.get('LLM_BASE_URL'))
modules = {name: importlib.util.find_spec(name) is not None for name in
           ('httpx', 'openai', 'langchain_openai', 'dotenv', 'PIL', 'reportlab', 'cairosvg')}
result = {'observed_utc': now(), 'credential_presence_only': presence,
          'safe_existing_configuration': safe, 'host_python_modules': modules,
          'cloud_api_call_performed': False,
          'agent_entry_point': 'src/agent/run.py -> Agent -> POST /prompt',
          'agent_llm': 'src/agent/src/agents/llm.py: ChatLLM(ChatOpenAI)',
          'agent_tools': 'Shopping operations; no existing telemetry query tools',
          'native_model_routing': 'One configured model; no fallback router exposed',
          'external_observer': 'artifacts/checkpoint1/checkpoint1_observe.py',
          'injector': 'faultctl.py -> src/faultctl/cli.py -> FaultClient.write',
          'injector_limit': 'HTTP and file transports both rewrite existing flag configuration',
          'deployment_history_limit': 'No deployment audit feed found; lifecycle events only',
          'artifact_mechanism': 'No existing checkpoint mechanism found; separate new artifacts directory'}
save(HOME / 'reconnaissance.json', result)
print(json.dumps(result, indent=2))
