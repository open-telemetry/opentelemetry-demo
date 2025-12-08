#!/usr/bin/env python3
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""
Extract and display image versions from Kubernetes manifests.
Used to show which services use which image versions in the production workflows.
"""

import yaml
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime


def extract_image_from_manifest(manifest_path: Path) -> Tuple[str, str, str]:
    """
    Extract service name, image, and version from a Kubernetes manifest.

    Returns:
        Tuple of (service_name, full_image, version_tag)
    """
    try:
        with open(manifest_path, 'r') as f:
            docs = list(yaml.safe_load_all(f))

        # Find Deployment resource
        for doc in docs:
            if doc and doc.get('kind') == 'Deployment':
                service_name = doc.get('metadata', {}).get('name', 'unknown')
                containers = doc.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])

                if containers:
                    image = containers[0].get('image', '')
                    # Extract version from image (format: registry/name:version)
                    if ':' in image:
                        version = image.split(':')[-1]
                    else:
                        version = 'latest'

                    return service_name, image, version

        return ('unknown', '', 'unknown')

    except Exception as e:
        print(f"Warning: Could not parse {manifest_path}: {e}", file=sys.stderr)
        return ('unknown', '', 'unknown')


def categorize_version(version: str, base_version: str) -> str:
    """
    Categorize a version tag relative to the base version.

    Returns:
        Category string: 'current', 'hotfix', 'older', 'external'
    """
    if not version or version == 'latest':
        return 'external'

    # Check if it's a hotfix version (e.g., 1.1.0-payment.1)
    if '-' in version and '.' in version.split('-')[-1]:
        return 'hotfix'

    # Check if it matches base version
    if version == base_version:
        return 'current'

    # Try to compare versions
    try:
        def parse_version(v):
            # Remove any suffix after '-'
            base = v.split('-')[0]
            parts = base.split('.')
            return tuple(int(p) for p in parts)

        current_parts = parse_version(version)
        base_parts = parse_version(base_version)

        if current_parts < base_parts:
            return 'older'
        elif current_parts > base_parts:
            return 'newer'
        else:
            return 'current'
    except:
        return 'unknown'


def get_service_versions() -> List[Tuple[str, str, str]]:
    """
    Scan all service manifests and extract image versions.

    Returns:
        List of (service_name, image, version) tuples
    """
    src_dir = Path('src')
    versions = []

    for service_dir in sorted(src_dir.iterdir()):
        if not service_dir.is_dir():
            continue

        # Look for [service]-k8s.yaml
        service_name = service_dir.name
        manifest_path = service_dir / f"{service_name}-k8s.yaml"

        if manifest_path.exists():
            service, image, version = extract_image_from_manifest(manifest_path)
            versions.append((service, image, version))

    return versions


def print_version_table(versions: List[Tuple[str, str, str]], base_version: str, format: str = 'markdown'):
    """
    Print a formatted table of service versions.

    Args:
        versions: List of (service_name, image, version) tuples
        base_version: The base SPLUNK-VERSION for comparison
        format: 'markdown', 'github' (for GitHub Actions summary), or 'plain'
    """
    if format == 'markdown' or format == 'github':
        print("| Service | Image Version | Status |")
        print("|---------|---------------|--------|")

        for service, image, version in versions:
            category = categorize_version(version, base_version)

            # Status emoji and text
            if category == 'current':
                status = f"✅ Current ({base_version})"
            elif category == 'hotfix':
                status = f"🔧 Hotfix"
            elif category == 'older':
                status = f"⚠️ Older"
            elif category == 'newer':
                status = f"🆕 Newer"
            elif category == 'external':
                status = f"📦 External"
            else:
                status = f"❓ Unknown"

            print(f"| `{service}` | `{version}` | {status} |")

    elif format == 'plain':
        max_service_len = max(len(s) for s, _, _ in versions)
        max_version_len = max(len(v) for _, _, v in versions)

        print(f"{'Service':<{max_service_len}}  {'Version':<{max_version_len}}  Status")
        print("-" * (max_service_len + max_version_len + 20))

        for service, image, version in versions:
            category = categorize_version(version, base_version)

            if category == 'current':
                status = f"Current ({base_version})"
            elif category == 'hotfix':
                status = f"Hotfix"
            elif category == 'older':
                status = f"Older"
            elif category == 'newer':
                status = f"Newer"
            elif category == 'external':
                status = f"External"
            else:
                status = f"Unknown"

            print(f"{service:<{max_service_len}}  {version:<{max_version_len}}  {status}")


def get_version_summary(versions: List[Tuple[str, str, str]], base_version: str) -> Dict[str, int]:
    """
    Get a summary count of version categories.

    Returns:
        Dict with counts: {'current': 5, 'hotfix': 1, 'older': 2, ...}
    """
    summary = {
        'current': 0,
        'hotfix': 0,
        'older': 0,
        'newer': 0,
        'external': 0,
        'unknown': 0
    }

    for _, _, version in versions:
        category = categorize_version(version, base_version)
        summary[category] = summary.get(category, 0) + 1

    return summary


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Extract and display image versions from manifests')
    parser.add_argument('--base-version', help='Base version for comparison (default: read from SPLUNK-VERSION)')
    parser.add_argument('--format', choices=['markdown', 'github', 'plain'], default='markdown',
                       help='Output format')
    parser.add_argument('--summary-only', action='store_true',
                       help='Only show summary counts, not full table')

    args = parser.parse_args()

    # Get base version
    if args.base_version:
        base_version = args.base_version
    else:
        try:
            with open('SPLUNK-VERSION', 'r') as f:
                base_version = f.read().strip()
        except FileNotFoundError:
            print("Error: SPLUNK-VERSION file not found and --base-version not provided", file=sys.stderr)
            sys.exit(1)

    # Get versions
    versions = get_service_versions()

    if not versions:
        print("No service manifests found", file=sys.stderr)
        sys.exit(1)

    # Show summary or full table
    if args.summary_only:
        summary = get_version_summary(versions, base_version)
        print(f"Base Version: {base_version}")
        print(f"Total Services: {len(versions)}")
        print(f"  - Current ({base_version}): {summary['current']}")
        print(f"  - Hotfixes: {summary['hotfix']}")
        print(f"  - Older versions: {summary['older']}")
        print(f"  - Newer versions: {summary['newer']}")
        print(f"  - External images: {summary['external']}")
        if summary['unknown'] > 0:
            print(f"  - Unknown: {summary['unknown']}")
    else:
        print_version_table(versions, base_version, args.format)


if __name__ == '__main__':
    main()
