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
    priority_services = []  # Services that must come first (namespace, RBAC, etc.)

    # Define critical resources that must be created first
    PRIORITY_ORDER = ['demo-namespace', 'demo-service-account']

    for service in config.get('services', []):
        name = service.get('name')
        if not name:
            continue

        # Apply filter if specified
        if filter_type:
            if not service.get(filter_type, False):
                continue

        # Separate priority services from regular services
        if name in PRIORITY_ORDER:
            priority_services.append(name)
        else:
            services.append(name)

    # Sort priority services by their defined order
    priority_services.sort(key=lambda x: PRIORITY_ORDER.index(x) if x in PRIORITY_ORDER else len(PRIORITY_ORDER))

    # Combine priority services first, then regular services
    all_services = priority_services + services

    # Output as space-separated list for shell consumption
    print(' '.join(all_services))

if __name__ == '__main__':
    main()
