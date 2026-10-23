"""Operator configuration, request limits, redaction, and read-only transports."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import tomllib
from datetime import datetime, timezone
from urllib import error, parse, request


class ToolError(Exception):
    def __init__(self, code, message, status='error'):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def utc_now():
    return datetime.now(timezone.utc)


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be an ISO 8601 string with timezone')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp must include a timezone')
    return dt.astimezone(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def digest(value):
    data = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def identifier(value, max_length=128):
    # Exclude query, shell, path, and PromQL syntax from identifiers.
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value) is not None and len(value) <= max_length


def finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('Non-finite observation')
    return number


class Config:
    def __init__(self, data, base_dir=None):
        self.data = data
        self.base_dir = Path(base_dir or '.').resolve()
        self.services = data.get('services', [])
        if not isinstance(self.services, list) or not self.services or not all(identifier(s) for s in self.services):
            raise ValueError('Configure an explicit services allowlist')
        self.limits = {
            'timeout_seconds': 10, 'retries': 1, 'max_window_seconds': 3600,
            'max_items': 100, 'max_response_bytes': 2097152,
            'max_samples': 2000, 'min_step_seconds': 15,
        }
        extra = data.get('limits', {})
        if set(extra) - set(self.limits):
            raise ValueError('Unknown limit')
        self.limits.update(extra)
        caps = {'timeout_seconds': 30, 'retries': 2, 'max_window_seconds': 86400,
                'max_items': 1000, 'max_response_bytes': 8388608,
                'max_samples': 10000, 'min_step_seconds': 300}
        for key, value in self.limits.items():
            minimum = 0 if key == 'retries' else 1
            if type(value) is not int or not minimum <= value <= caps[key]:
                raise ValueError('Invalid limit: ' + key)
        self.origin = data.get('origin', 'backend')
        if self.origin not in ('backend', 'fixture'):
            raise ValueError('origin must be backend or fixture')
        self.secrets = []
        self.headers = {}
        for name in ('prometheus', 'jaeger', 'opensearch'):
            section = self.section(name)
            endpoint = section.get('endpoint', '')
            if endpoint:
                url = parse.urlsplit(endpoint)
                if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
                    raise ValueError('Endpoint must be HTTP(S) without credentials, query or fragment')
            env = section.get('bearer_token_env')
            if env:
                if not identifier(env):
                    raise ValueError('Invalid token environment-variable name')
                token = os.environ.get(env)
                if not token:
                    raise ValueError('Configured authentication environment variable is missing')
                if not endpoint or parse.urlsplit(endpoint).scheme != 'https':
                    raise ValueError('Authenticated endpoints require HTTPS')
                self.secrets.append(token)
                self.headers[name] = {'Authorization': 'Bearer ' + token}
        docker = self.section('docker')
        if docker.get('transport', 'native') not in ('native', 'wsl'):
            raise ValueError('Docker transport must be native or wsl')
        if not identifier(docker.get('project', 'opentelemetry-demo')) or not identifier(docker.get('distro', 'Ubuntu')):
            raise ValueError('Invalid Docker scope')
        logs = self.section('opensearch')
        # Only index wildcards and dotted field names are accepted, never DSL or URLs.
        if not re.fullmatch(r'[a-z0-9_][a-z0-9_.*-]*', logs.get('index', 'otel-logs-*')):
            raise ValueError('Invalid log index')
        for key, default in (('service_field', 'resource.service.name'), ('service_query_field', 'resource.service.name'), ('time_field', 'observedTimestamp')):
            if not identifier(logs.get(key, default)):
                raise ValueError('Invalid log field')

    @classmethod
    def load(cls, file):
        file = Path(file)
        with file.open('rb') as stream:
            return cls(tomllib.load(stream), file.resolve().parent)

    def section(self, key):
        value = self.data.get(key, {})
        if not isinstance(value, dict):
            raise ValueError('Invalid configuration section')
        return value

    def endpoint(self, name):
        value = self.section(name).get('endpoint', '').rstrip('/')
        if not value:
            raise ToolError('not_configured', name + ' endpoint is not configured', 'unavailable')
        return value

    def clean(self, value):
        if isinstance(value, dict):
            # Structured credentials are removed before text rendering.
            return {k: ('[REDACTED]' if re.search(r'(?i)api[_-]?key|password|passwd|secret|token|authorization', k) else self.clean(v)) for k, v in value.items()}
        if isinstance(value, list):
            return [self.clean(v) for v in value]
        if not isinstance(value, str):
            return value
        for secret in self.secrets:
            value = value.replace(secret, '[REDACTED]')
        # Mask common credentials, bearer tokens, URL userinfo, query secrets, and email PII.
        value = re.sub(r'(?i)\b(?:bearer|basic)\s+[A-Za-z0-9+/=._-]+', '[REDACTED AUTH]', value)
        value = re.sub(r'''(?i)((?:api[_-]?key|password|passwd|secret|token|authorization)["']?\s*[=:]\s*)(?:"[^"]*"|'[^']*'|[^\s&,;]+)''', r'\1[REDACTED]', value)
        value = re.sub(r'(https?://)[^/\s@]+@', r'\1[REDACTED]@', value)
        value = re.sub(r"[A-Za-z0-9.!#$%&'*+/=?^_\x60{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", '[REDACTED EMAIL]', value)
        return value[:4096]


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def decode_response(backend, raw):
    if backend != 'jaeger':
        return json.loads(raw, parse_constant=finite)
    if not raw.strip():
        frames = []
    else:
        try:
            frames = [json.loads(raw, parse_constant=finite)]
        except json.JSONDecodeError:
            lines = [line for line in raw.splitlines() if line.strip()]
            if len(lines) < 2:
                raise
            frames = [json.loads(line, parse_constant=finite) for line in lines]
    resources = []
    for frame in frames:
        if not isinstance(frame, dict):
            raise ToolError('malformed_response', 'Invalid Jaeger stream envelope')
        if frame.get('error'):
            raise ToolError('query_failed', 'Jaeger stream reported a query error; partial chunks are not treated as complete evidence')
        result = frame.get('result')
        if not isinstance(result, dict):
            raise ToolError('malformed_response', 'Missing Jaeger result envelope')
        spans = result.get('resourceSpans') or []
        if not isinstance(spans, list):
            raise ToolError('malformed_response', 'Invalid Jaeger resourceSpans list')
        resources.extend(spans)
    return {'result': {'resourceSpans': resources}}


class HTTP:
    def __init__(self, config):
        self.config = config
        self.opener = request.build_opener(request.ProxyHandler({}), NoRedirect())

    def json(self, backend, route, params=None, body=None):
        url = self.config.endpoint(backend) + route
        if params:
            url += '?' + parse.urlencode(params)
        headers = {'Accept': 'application/json', **self.config.headers.get(backend, {})}
        data = None
        if body is not None:
            if backend != 'opensearch' or not route.endswith('/_search'):
                raise ToolError('forbidden_method', 'Only the log search supports POST')
            data = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        req = request.Request(url, data=data, headers=headers)
        size = self.config.limits['max_response_bytes']
        for attempt in range(self.config.limits['retries'] + 1):
            try:
                with self.opener.open(req, timeout=self.config.limits['timeout_seconds']) as response:
                    raw = response.read(size + 1)
                if len(raw) > size:
                    raise ToolError('response_too_large', 'Response exceeds configured byte limit')
                return decode_response(backend, raw)
            except error.HTTPError as exc:
                retry = exc.code in (429, 502, 503, 504)
                code = 'http_' + str(exc.code)
                exc.close()
            except (error.URLError, TimeoutError, OSError):
                retry, code = True, 'connection_failed'
            except (UnicodeError, ValueError, RecursionError):
                raise ToolError('malformed_response', 'Backend did not return valid JSON') from None
            if not retry or attempt == self.config.limits['retries']:
                raise ToolError(code, 'Backend request failed; check connectivity, credentials, and endpoint', 'unavailable')
            time.sleep(0.1 * (attempt + 1))


class Docker:
    def __init__(self, config):
        self.config = config

    def run(self, args):
        if not args or args[0] not in ('ps', 'inspect', 'events'):
            raise ToolError('forbidden_command', 'Docker command is outside the read-only allowlist')
        section = self.config.section('docker')
        prefix = ['docker'] if section.get('transport', 'native') == 'native' else ['wsl', '-d', section.get('distro', 'Ubuntu'), '--', 'docker']
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                process = subprocess.Popen(prefix + args, stdout=out, stderr=err, shell=False)
                try:
                    process.wait(timeout=self.config.limits['timeout_seconds'])
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise ToolError('docker_timeout', 'Docker read timed out', 'unavailable') from None
            except OSError:
                raise ToolError('docker_unavailable', 'Docker transport is not available', 'unavailable') from None
            if process.returncode:
                raise ToolError('docker_failed', 'Docker read failed; check daemon, transport, and permissions', 'unavailable')
            out.seek(0)
            raw = out.read(self.config.limits['max_response_bytes'] + 1)
        if len(raw) > self.config.limits['max_response_bytes']:
            raise ToolError('response_too_large', 'Docker response exceeds configured byte limit')
        try:
            return raw.decode('utf-8')
        except UnicodeError:
            raise ToolError('malformed_response', 'Docker response is not UTF-8') from None
