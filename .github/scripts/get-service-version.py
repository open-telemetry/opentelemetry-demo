#!/usr/bin/env python3
"""
Get version for a specific service from .service-versions.yaml

Usage:
    get-service-version.py <service-name> <default-version>

Returns:
    - Service-specific version from .service-versions.yaml if exists
    - Default version if service not found or file doesn't exist
"""

import yaml
import sys
import os

def main():
    if len(sys.argv) < 3:
        print("Usage: get-service-version.py <service-name> <default-version>", file=sys.stderr)
        sys.exit(1)

    service_name = sys.argv[1]
    default_version = sys.argv[2]

    # Check if .service-versions.yaml exists (test/dev builds only)
    if not os.path.exists('.service-versions.yaml'):
        print(default_version)
        return 0

    try:
        # Read .service-versions.yaml
        with open('.service-versions.yaml', 'r') as f:
            config = yaml.safe_load(f)

        services = config.get('services', {})
        service_version = services.get(service_name, default_version)

        print(service_version)
        return 0

    except Exception as e:
        # If any error, fall back to default version
        print(default_version, file=sys.stderr)
        print(default_version)
        return 0

if __name__ == '__main__':
    sys.exit(main())
