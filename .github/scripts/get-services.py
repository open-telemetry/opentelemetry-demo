#!/usr/bin/env python3
"""
Helper script to read services from services.yaml configuration file.
Usage: ./get-services.py [--manifest|--build]
"""

import yaml
import sys

def main():
    # Determine filter type
    filter_type = None
    if len(sys.argv) > 1:
        if sys.argv[1] == '--manifest':
            filter_type = 'manifest'
        elif sys.argv[1] == '--build':
            filter_type = 'build'

    # Read services.yaml
    try:
        with open('services.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: services.yaml not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading services.yaml: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract service names based on filter
    services = []
    for service in config.get('services', []):
        name = service.get('name')
        if not name:
            continue

        # Apply filter if specified
        if filter_type:
            if not service.get(filter_type, False):
                continue

        services.append(name)

    # Output as space-separated list for shell consumption
    print(' '.join(services))

if __name__ == '__main__':
    main()
