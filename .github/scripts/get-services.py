#!/usr/bin/env python3
"""
Get list of services from services.yaml

Usage:
    get-services.py --manifest    # Returns services with manifest: true
    get-services.py --build       # Returns services with build: true
    get-services.py --all         # Returns all services
"""

import yaml
import sys

def main():
    filter_type = sys.argv[1] if len(sys.argv) > 1 else '--all'

    # Read services.yaml
    with open('services.yaml', 'r') as f:
        config = yaml.safe_load(f)

    services = config.get('services', [])
    result = []

    for svc in services:
        name = svc.get('name')
        if not name:
            continue

        if filter_type == '--manifest':
            if svc.get('manifest', False):
                result.append(name)
        elif filter_type == '--build':
            if svc.get('build', False):
                result.append(name)
        elif filter_type == '--all':
            result.append(name)

    # Output as space-separated list
    print(' '.join(result))
    return 0

if __name__ == '__main__':
    sys.exit(main())
