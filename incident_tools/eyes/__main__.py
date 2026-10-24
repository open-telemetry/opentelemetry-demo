"""Read-only Eyes workflow. Run from the repository root."""
import argparse
import json
import os
from pathlib import Path
import time
import uuid

from incident_tools.f02 import ObservabilityTools
from .core import Detector, Investigator, Store
from .runtime import Router, architecture, export, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    watch = sub.add_parser('watch')
    watch.add_argument('--polls', type=int, default=0, help='0: until Ctrl+C')
    watch.add_argument('--detect-only', action='store_true', help='Queue incidents without inference')
    sub.add_parser('list')
    investigate = sub.add_parser('investigate')
    investigate.add_argument('--id', required=True, help='Existing queued/incomplete incident ID')
    diagram = sub.add_parser('diagram')
    diagram.add_argument('--output', required=True, help='New SVG file')
    args = parser.parse_args()
    lock = None
    store = None
    try:
        cfg, settings, f02_config, directory = load(args.config)
        if args.command == 'diagram':
            with Path(args.output).open('x', encoding='utf-8') as stream:
                stream.write(architecture())
            return 0
        tools = ObservabilityTools(f02_config)
        if not set(settings['services']) <= set(tools.config.services) or settings['window_seconds'] > tools.config.limits['max_window_seconds']:
            raise ValueError('Workflow scope exceeds F02 limits')
        store = Store(directory)
        if args.command == 'list':
            print(json.dumps(store.incidents(), indent=2))
            return 0
        lock = Path(directory) / 'operator.lock'
        try:
            with lock.open('x', encoding='utf-8') as stream:
                stream.write(str(os.getpid()))
        except FileExistsError:
            lock = None
            raise ValueError('Another operator process or stale lock exists')
        model = None if args.command == 'watch' and args.detect_only else Router(cfg['models'])
        for slot in ('local', 'cloud'):
            secret = os.environ.get(cfg.get('models', {}).get(slot, {}).get('api_key_env', ''))
            if secret:
                tools.config.secrets.append(secret)
        detector = Detector(tools, store, settings)
        iteration = 0
        while True:
            if args.command == 'watch':
                check = detector.poll()
                with (Path(directory) / ('poll-' + uuid.uuid4().hex + '.json')).open('x', encoding='utf-8') as stream:
                    json.dump(check, stream, indent=2)
                print(json.dumps(check), flush=True)
                candidates = [i for i in store.incidents() if i['investigation'] == 'queued']
            else:
                candidates = [i for i in store.incidents() if i['id'] == args.id and i['investigation'] in ('queued', 'incomplete')]
                if not candidates:
                    raise ValueError('Incident is not queued/incomplete; interrupted running jobs need operator review')
            if model and candidates:
                incident = candidates[0]
                run = Investigator(tools, store, model, settings).run(incident)
                destination = Path(directory) / (incident['id'] + '-' + uuid.uuid4().hex[:8])
                export(run, destination)
                print(json.dumps({'incident': incident['id'], 'artifacts': str(destination), 'stop_reason': run['stop_reason']}), flush=True)
            if args.command != 'watch':
                return 0 if run['stop_reason'] == 'model_finished' else 1
            iteration += 1
            if args.polls and iteration >= args.polls:
                return 0
            time.sleep(settings['poll_seconds'])
    except KeyboardInterrupt:
        return 130
    except Exception:
        print('Eyes stopped: check configuration, provider availability, evidence/state permissions, and operator.lock. No successful investigation is claimed.', flush=True)
        return 1
    finally:
        if store:
            store.db.close()
        if lock:
            lock.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
