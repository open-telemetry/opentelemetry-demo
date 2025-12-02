#!/usr/bin/env python3
"""
Helper script to get the version for a specific service from .service-versions.yaml
Falls back to SPLUNK-VERSION if the version tracking file doesn't exist
"""

import yaml
import sys
import os

def get_service_version(service_name, fallback_version):
    """Get the version for a specific service."""

    # Check if .service-versions.yaml exists
    if not os.path.exists('.service-versions.yaml'):
        # Fall back to single version for all services
        return fallback_version

    try:
        # Read service versions
        with open('.service-versions.yaml', 'r') as f:
            version_config = yaml.safe_load(f)

        # Get version for this service
        services = version_config.get('services', {})
        if service_name in services:
            return services[service_name]
        else:
            # Use default version if service not found
            return version_config.get('default_version', fallback_version)

    except Exception as e:
        # On any error, fall back to single version
        print(f"Warning: Error reading .service-versions.yaml: {e}", file=sys.stderr)
        return fallback_version

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: get-service-version.py <service_name> <fallback_version>", file=sys.stderr)
        sys.exit(1)

    service_name = sys.argv[1]
    fallback_version = sys.argv[2]

    version = get_service_version(service_name, fallback_version)
    print(version)
