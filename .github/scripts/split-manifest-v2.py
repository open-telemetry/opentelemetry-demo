#!/usr/bin/env python3
"""
Split the monolithic Kubernetes manifest into per-service manifests.
Properly parses YAML and groups all resource types by service.
"""

import os
import sys
import yaml
from pathlib import Path
from collections import defaultdict

def load_yaml_documents(file_path):
    """Load all documents from a multi-document YAML file."""
    with open(file_path, 'r') as f:
        docs = list(yaml.safe_load_all(f))
    return [doc for doc in docs if doc is not None]

def get_service_name_from_labels(resource):
    """Extract service name from Kubernetes labels."""
    if not resource or not isinstance(resource, dict):
        return None

    metadata = resource.get('metadata', {})
    labels = metadata.get('labels', {})

    # Try different label patterns
    label_keys = [
        'app.kubernetes.io/component',
        'app.kubernetes.io/name',
        'app',
        'component',
        'service'
    ]

    for key in label_keys:
        if key in labels:
            value = labels[key]
            # Skip generic values
            if value not in ['opentelemetry-demo', 'default', 'true', 'false']:
                return value

    return None

def get_service_name_from_metadata(resource):
    """Extract service name from metadata name."""
    if not resource or not isinstance(resource, dict):
        return None

    metadata = resource.get('metadata', {})
    name = metadata.get('name', '')

    # Skip if it's a generic name
    if name in ['otel-demo', 'opentelemetry-demo', 'default']:
        return name

    # Common patterns in names
    # Remove common suffixes
    for suffix in ['-service', '-deployment', '-statefulset', '-configmap',
                   '-secret', '-serviceaccount', '-pdb', '-hpa']:
        if name.endswith(suffix):
            return name[:-len(suffix)]

    return name if name else None

def get_service_name_from_selector(resource):
    """Extract service name from selector or matchLabels."""
    if not resource or not isinstance(resource, dict):
        return None

    spec = resource.get('spec', {})

    # For Services
    selector = spec.get('selector', {})
    if selector:
        for key in ['app', 'component', 'app.kubernetes.io/component']:
            if key in selector:
                value = selector[key]
                if value not in ['opentelemetry-demo', 'default']:
                    return value

    # For Deployments/StatefulSets
    match_labels = spec.get('selector', {}).get('matchLabels', {})
    if match_labels:
        for key in ['app', 'component', 'app.kubernetes.io/component']:
            if key in match_labels:
                value = match_labels[key]
                if value not in ['opentelemetry-demo', 'default']:
                    return value

    return None

def determine_service_name(resource):
    """Determine the service name for a resource."""
    kind = resource.get('kind', 'Unknown')

    # Try labels first
    service = get_service_name_from_labels(resource)
    if service:
        return service

    # Try selector
    service = get_service_name_from_selector(resource)
    if service:
        return service

    # Try metadata name
    service = get_service_name_from_metadata(resource)
    if service:
        return service

    return 'shared'  # For namespace, shared resources, etc.

def resource_to_yaml(resource):
    """Convert a resource dict back to YAML string."""
    return yaml.dump(resource, default_flow_style=False, sort_keys=False)

def main():
    manifest_path = Path('kubernetes/opentelemetry-demo.yaml')
    src_dir = Path('src')

    if not manifest_path.exists():
        print(f"❌ Error: {manifest_path} not found")
        sys.exit(1)

    print(f"📖 Reading {manifest_path}...")
    try:
        documents = load_yaml_documents(manifest_path)
        print(f"   Found {len(documents)} Kubernetes resources")
    except Exception as e:
        print(f"❌ Error parsing YAML: {e}")
        sys.exit(1)

    # Group resources by service
    service_resources = defaultdict(list)
    resource_types = defaultdict(int)

    print("\n🔍 Analyzing resources...")
    for doc in documents:
        if not doc:
            continue

        kind = doc.get('kind', 'Unknown')
        resource_types[kind] += 1

        service_name = determine_service_name(doc)
        service_resources[service_name].append(doc)

        metadata = doc.get('metadata', {})
        name = metadata.get('name', 'unnamed')
        print(f"   ✓ {service_name}: {kind}/{name}")

    print("\n📊 Resource type summary:")
    for kind, count in sorted(resource_types.items()):
        print(f"   {kind}: {count}")

    # Create manifests
    print("\n📝 Creating service manifests...")
    created_dirs = []
    updated_services = []

    for service_name, resources in sorted(service_resources.items()):
        service_dir = src_dir / service_name

        # Create directory if needed
        if not service_dir.exists():
            service_dir.mkdir(parents=True, exist_ok=True)
            created_dirs.append(service_name)
            print(f"   📁 Created directory: {service_dir}")

        # Create manifest file
        manifest_file = service_dir / f"{service_name}-k8s.yaml"

        with open(manifest_file, 'w') as f:
            f.write(f"# Kubernetes manifest for {service_name}\n")
            f.write(f"# Auto-generated from opentelemetry-demo.yaml\n")
            f.write(f"# Contains {len(resources)} resource(s)\n")

            for i, resource in enumerate(resources):
                f.write("---\n")
                f.write(resource_to_yaml(resource))

        updated_services.append(service_name)

        # Show resource breakdown
        kinds = [r.get('kind', 'Unknown') for r in resources]
        kind_counts = {}
        for k in kinds:
            kind_counts[k] = kind_counts.get(k, 0) + 1
        kind_summary = ', '.join([f"{k}({v})" for k, v in kind_counts.items()])

        print(f"   ✓ Created: {manifest_file}")
        print(f"      Resources: {kind_summary}")

    # Check for missing manifests
    print("\n🔍 Checking for services without manifests...")
    all_src_dirs = [d.name for d in src_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
    dirs_without_manifests = [d for d in all_src_dirs if d not in updated_services]

    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)

    print(f"\n✅ Services with manifests: {len(updated_services)}")
    for service in sorted(updated_services):
        status = "📁 NEW" if service in created_dirs else "🔄 UPDATED"
        resource_count = len(service_resources[service])
        print(f"   {status} {service} ({resource_count} resources)")

    if created_dirs:
        print(f"\n📁 New directories created: {len(created_dirs)}")
        for service in sorted(created_dirs):
            print(f"   - {service}")

    if dirs_without_manifests:
        print(f"\n⚠️  Directories without manifests: {len(dirs_without_manifests)}")
        for service in sorted(dirs_without_manifests):
            print(f"   - {service}")

    print("\n" + "="*70)

    # Generate GitHub Actions list
    print("\n📋 Updated SERVICES array for stitch-manifests.sh:")
    print("SERVICES=(")
    for service in sorted(set(updated_services + all_src_dirs)):
        print(f'    "{service}"')
    print(")")

if __name__ == '__main__':
    main()
