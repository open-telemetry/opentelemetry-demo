"""Operator CLI and newline-delimited JSON tool-call adapter."""
import argparse
import json
from pathlib import Path
import sys

from .boundary import Config
from .tools import ObservabilityTools


def emit(value, output=None):
    text = json.dumps(value, indent=2 if output else None, allow_nan=False)
    if output:
        with Path(output).open('x', encoding='utf-8') as stream:
            stream.write(text + '\n')
    else:
        print(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, help='Operator-controlled TOML; never agent-supplied')
    sub = parser.add_subparsers(dest='command', required=True)
    schemas = sub.add_parser('schemas', help='Print agent-callable JSON function schemas')
    schemas.add_argument('--output')
    call = sub.add_parser('call', help='Call one read-only tool')
    call.add_argument('tool')
    call.add_argument('--service', required=True)
    call.add_argument('--start', required=True)
    call.add_argument('--end', required=True)
    call.add_argument('--metric')
    call.add_argument('--trace-id')
    call.add_argument('--limit', type=int)
    call.add_argument('--step-seconds', type=int)
    call.add_argument('--output', help='Create a NEW JSON evidence file; never overwrite')
    sub.add_parser('serve', help='Read {tool,arguments} JSON per stdin line; emit one result per line')
    args = parser.parse_args()
    try:
        tools = ObservabilityTools(Config.load(args.config))
        if args.command == 'schemas':
            emit(tools.schemas(), args.output)
            return 0
        if args.command == 'call':
            parameters = {k: getattr(args, k) for k in ('service', 'start', 'end', 'metric', 'trace_id', 'limit', 'step_seconds') if getattr(args, k) is not None}
            result = tools.call(args.tool, parameters)
            emit(result, args.output)
            return 1 if result['status'] in ('error', 'invalid_request', 'unavailable') else 0
        while True:
            line = sys.stdin.buffer.readline(tools.config.limits['max_response_bytes'] + 1)
            if not line:
                return 0
            if len(line) > tools.config.limits['max_response_bytes']:
                emit({'status': 'invalid_request', 'error': {'code': 'input_too_large'}})
                return 1
            try:
                envelope = json.loads(line)
                if not isinstance(envelope, dict) or set(envelope) != {'tool', 'arguments'}:
                    raise ValueError('Invalid tool envelope')
                emit(tools.call(envelope['tool'], envelope['arguments']))
            except (ValueError, TypeError, RecursionError):
                emit({'status': 'invalid_request', 'error': {'code': 'invalid_envelope'}})
    except (ValueError, TypeError, KeyError, OSError):
        print('Configuration or output error. Check TOML, required environment variables, and use a new writable output path.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
