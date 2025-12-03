#!/usr/bin/env python3
"""
Version bump script for production releases
Supports: major, minor, patch, and hotfix version bumps
"""

import sys
import re

def parse_version(version_str):
    """Parse a semantic version string into components."""
    # Remove 'v' prefix if present
    version_str = version_str.lstrip('v')

    # Match semantic version with optional prerelease/metadata
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$', version_str)
    if not match:
        raise ValueError(f"Invalid version format: {version_str}")

    major, minor, patch, prerelease = match.groups()
    return {
        'major': int(major),
        'minor': int(minor),
        'patch': int(patch),
        'prerelease': prerelease or ''
    }

def bump_version(current_version, bump_type):
    """Bump version according to bump_type."""
    parts = parse_version(current_version)

    if bump_type == 'major':
        parts['major'] += 1
        parts['minor'] = 0
        parts['patch'] = 0
        parts['prerelease'] = ''
    elif bump_type == 'minor':
        parts['minor'] += 1
        parts['patch'] = 0
        parts['prerelease'] = ''
    elif bump_type == 'patch':
        parts['patch'] += 1
        parts['prerelease'] = ''
    elif bump_type == 'none':
        # No bump, return current version
        return current_version
    else:
        raise ValueError(f"Invalid bump type: {bump_type}. Must be 'major', 'minor', 'patch', or 'none'")

    # Reconstruct version string
    new_version = f"{parts['major']}.{parts['minor']}.{parts['patch']}"
    if parts['prerelease']:
        new_version += f"-{parts['prerelease']}"

    return new_version

def create_hotfix_version(base_version, service_name, hotfix_number=1):
    """Create a hotfix version string."""
    # Remove any existing prerelease suffix
    parts = parse_version(base_version)
    base = f"{parts['major']}.{parts['minor']}.{parts['patch']}"

    return f"{base}-hotfix-{service_name}-{hotfix_number}"

def get_next_hotfix_number(current_version, service_name):
    """Extract hotfix number from current version if it exists."""
    parts = parse_version(current_version)
    prerelease = parts.get('prerelease', '')

    # Match pattern: hotfix-{service}-{number}
    match = re.match(rf'hotfix-{re.escape(service_name)}-(\d+)', prerelease)
    if match:
        return int(match.group(1)) + 1
    return 1

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: bump-version.py <current_version> <bump_type> [service_name]", file=sys.stderr)
        print("  bump_type: major, minor, patch, none", file=sys.stderr)
        print("  service_name: required for hotfix bumps", file=sys.stderr)
        sys.exit(1)

    current_version = sys.argv[1]
    bump_type = sys.argv[2]
    service_name = sys.argv[3] if len(sys.argv) > 3 else None

    try:
        if bump_type == 'hotfix':
            if not service_name:
                print("Error: service_name required for hotfix bumps", file=sys.stderr)
                sys.exit(1)
            hotfix_num = get_next_hotfix_number(current_version, service_name)
            new_version = create_hotfix_version(current_version, service_name, hotfix_num)
        else:
            new_version = bump_version(current_version, bump_type)

        print(new_version)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
