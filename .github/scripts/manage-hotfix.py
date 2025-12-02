#!/usr/bin/env python3
"""
Hotfix version management script for production builds
Manages .hotfix.yaml which tracks service-specific hotfixes
"""

import yaml
import sys
import os
from pathlib import Path

HOTFIX_FILE = '.hotfix.yaml'

def get_current_base_version():
    """Get the current SPLUNK-VERSION."""
    with open('SPLUNK-VERSION', 'r') as f:
        return f.read().strip()

def load_hotfix_data():
    """Load existing hotfix data or create new structure."""
    if not os.path.exists(HOTFIX_FILE):
        return None

    try:
        with open(HOTFIX_FILE, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Warning: Error reading {HOTFIX_FILE}: {e}", file=sys.stderr)
        return None

def save_hotfix_data(data):
    """Save hotfix data to file."""
    with open(HOTFIX_FILE, 'w') as f:
        f.write('# Production Hotfix Tracking\n')
        f.write('# This file tracks hotfixes applied to the current base version\n')
        f.write('# Cleared automatically on full releases (minor/major bumps)\n')
        f.write('# DO NOT EDIT MANUALLY\n\n')
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

def add_hotfix(service_name):
    """Add or increment a hotfix for a service."""
    base_version = get_current_base_version()
    hotfix_data = load_hotfix_data()

    # If no existing hotfix file, or base version changed, start fresh
    if not hotfix_data or hotfix_data.get('base_version') != base_version:
        hotfix_data = {
            'base_version': base_version,
            'hotfixes': {}
        }

    # Get current hotfix number for this service, increment
    current_hotfix = hotfix_data['hotfixes'].get(service_name, 0)
    new_hotfix = current_hotfix + 1
    hotfix_data['hotfixes'][service_name] = new_hotfix

    save_hotfix_data(hotfix_data)

    # Return the full hotfix version tag
    hotfix_version = f"{base_version}-hotfix-{service_name}-{new_hotfix}"
    print(hotfix_version)
    return hotfix_version

def clear_hotfixes():
    """Clear all hotfixes (called on full releases)."""
    if os.path.exists(HOTFIX_FILE):
        os.remove(HOTFIX_FILE)
        print(f"Cleared {HOTFIX_FILE}")
    else:
        print(f"No {HOTFIX_FILE} to clear")

def get_service_version(service_name):
    """Get the version for a service (with hotfix if applicable)."""
    base_version = get_current_base_version()
    hotfix_data = load_hotfix_data()

    # If no hotfix data or base version mismatch, return base version
    if not hotfix_data or hotfix_data.get('base_version') != base_version:
        print(base_version)
        return base_version

    # Check if this service has a hotfix
    hotfix_num = hotfix_data.get('hotfixes', {}).get(service_name)
    if hotfix_num:
        version = f"{base_version}-hotfix-{service_name}-{hotfix_num}"
        print(version)
        return version
    else:
        print(base_version)
        return base_version

def show_status():
    """Show current hotfix status."""
    base_version = get_current_base_version()
    hotfix_data = load_hotfix_data()

    print(f"Base version: {base_version}")

    if not hotfix_data:
        print("No hotfixes applied")
        return

    if hotfix_data.get('base_version') != base_version:
        print(f"Warning: Hotfix file is for version {hotfix_data.get('base_version')}, but current is {base_version}")
        print("Hotfix file should be cleared")
        return

    hotfixes = hotfix_data.get('hotfixes', {})
    if not hotfixes:
        print("No hotfixes applied")
    else:
        print(f"Active hotfixes ({len(hotfixes)}):")
        for service, num in hotfixes.items():
            print(f"  - {service}: hotfix-{num} (version: {base_version}-hotfix-{service}-{num})")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: manage-hotfix.py <command> [args]", file=sys.stderr)
        print("Commands:", file=sys.stderr)
        print("  add <service_name>     - Add/increment hotfix for service", file=sys.stderr)
        print("  clear                  - Clear all hotfixes", file=sys.stderr)
        print("  get <service_name>     - Get version for service (with hotfix if applicable)", file=sys.stderr)
        print("  status                 - Show current hotfix status", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == 'add':
            if len(sys.argv) != 3:
                print("Error: 'add' requires service name", file=sys.stderr)
                sys.exit(1)
            add_hotfix(sys.argv[2])

        elif command == 'clear':
            clear_hotfixes()

        elif command == 'get':
            if len(sys.argv) != 3:
                print("Error: 'get' requires service name", file=sys.stderr)
                sys.exit(1)
            get_service_version(sys.argv[2])

        elif command == 'status':
            show_status()

        else:
            print(f"Error: Unknown command '{command}'", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
