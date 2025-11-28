#!/usr/bin/env python3
"""
Split the monolithic Kubernetes manifest into per-service manifests.
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict

def parse_yaml_documents(file_path):
    """Parse a multi-document YAML file into individual documents."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Split by '---' but keep track of document boundaries
    documents = []
    current_doc = []

    for line in content.split('\n'):
        if line.strip() == '---':
            if current_doc:
                documents.append('\n'.join(current_doc))
                current_doc = []
        else:
            current_doc.append(line)

    # Add the last document
    if current_doc:
        documents.append('\n'.join(current_doc))

    return documents

def extract_service_name(doc):
    """Extract service name from a Kubernetes resource."""
    # Look for common patterns to identify service name
    patterns = [
        r'app\.kubernetes\.io/component:\s*([^\s]+)',
        r'app\.kubernetes\.io/name:\s*([^\s]+)',
        r'component:\s*([^\s]+)',
        r'app:\s*([^\s]+)',
        r'name:\s*([^\s]+)'
    ]

    # Also check metadata.name for potential service name
    name_match = re.search(r'^  name:\s*([^\s]+)', doc, re.MULTILINE)

    for pattern in patterns:
        match = re.search(pattern, doc)
        if match:
            service_name = match.group(1)
            # Skip generic names
            if service_name not in ['opentelemetry-demo', 'default', 'true', 'false']:
                return service_name

    # Fallback to metadata.name if found
    if name_match:
        return name_match.group(1)

    return 'unknown'

def get_resource_type(doc):
    """Get the Kubernetes resource type."""
    match = re.search(r'^kind:\s*([^\s]+)', doc, re.MULTILINE)
    return match.group(1) if match else 'Unknown'

def main():
    # Paths
    manifest_path = Path('kubernetes/opentelemetry-demo.yaml')
    src_dir = Path('src')

    if not manifest_path.exists():
        print(f"❌ Error: {manifest_path} not found")
        sys.exit(1)

    print(f"📖 Reading {manifest_path}...")
    documents = parse_yaml_documents(manifest_path)
    print(f"   Found {len(documents)} Kubernetes resources")

    # Group documents by service
    service_docs = defaultdict(list)
    unknown_docs = []

    print("\n🔍 Analyzing resources...")
    for doc in documents:
        doc = doc.strip()
        if not doc or doc.startswith('#'):
            continue

        service_name = extract_service_name(doc)
        resource_type = get_resource_type(doc)

        if service_name == 'unknown':
            unknown_docs.append((doc, resource_type))
            print(f"   ⚠️  Could not identify service for {resource_type}")
        else:
            service_docs[service_name].append(doc)
            print(f"   ✓ {service_name}: {resource_type}")

    # Create service manifests
    print("\n📝 Creating service manifests...")
    created_dirs = []
    existing_services = []
    services_with_manifests = []

    for service_name, docs in sorted(service_docs.items()):
        service_dir = src_dir / service_name

        # Create directory if it doesn't exist
        if not service_dir.exists():
            service_dir.mkdir(parents=True, exist_ok=True)
            created_dirs.append(service_name)
            print(f"   📁 Created directory: {service_dir}")
        else:
            existing_services.append(service_name)

        # Create manifest file
        manifest_file = service_dir / f"{service_name}-k8s.yaml"

        with open(manifest_file, 'w') as f:
            f.write(f"# Kubernetes manifest for {service_name}\n")
            f.write(f"# Auto-generated from opentelemetry-demo.yaml\n")
            f.write("---\n")

            for i, doc in enumerate(docs):
                if i > 0:
                    f.write("\n---\n")
                f.write(doc)
                if not doc.endswith('\n'):
                    f.write('\n')

        services_with_manifests.append(service_name)
        print(f"   ✓ Created: {manifest_file} ({len(docs)} resources)")

    # Handle unknown documents
    if unknown_docs:
        print(f"\n⚠️  Found {len(unknown_docs)} resources without clear service association")
        unknown_file = Path('kubernetes/unknown-resources.yaml')
        with open(unknown_file, 'w') as f:
            f.write("# Resources that could not be associated with a specific service\n")
            f.write("# Review these manually and assign to appropriate services\n")
            f.write("---\n")
            for i, (doc, resource_type) in enumerate(unknown_docs):
                if i > 0:
                    f.write("\n---\n")
                f.write(doc)
                if not doc.endswith('\n'):
                    f.write('\n')
        print(f"   Saved to: {unknown_file}")

    # Check for src/ directories without manifests
    print("\n🔍 Checking for services without manifests...")
    all_src_dirs = [d.name for d in src_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
    dirs_without_manifests = [d for d in all_src_dirs if d not in services_with_manifests]

    # Generate summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)

    print(f"\n✅ Services with manifests created: {len(services_with_manifests)}")
    for service in sorted(services_with_manifests):
        status = "📁 NEW" if service in created_dirs else "✓"
        print(f"   {status} {service}")

    if created_dirs:
        print(f"\n📁 New directories created: {len(created_dirs)}")
        for service in sorted(created_dirs):
            print(f"   - {service}")

    if dirs_without_manifests:
        print(f"\n⚠️  Directories without manifests: {len(dirs_without_manifests)}")
        for service in sorted(dirs_without_manifests):
            print(f"   - {service}")

    if unknown_docs:
        print(f"\n⚠️  Unassigned resources: {len(unknown_docs)}")
        print(f"   Review: kubernetes/unknown-resources.yaml")

    print("\n" + "="*60)

    # Generate lists for GitHub Actions
    print("\n📋 For GitHub Actions workflow:")
    print("\nServices to add to SERVICES array in stitch-manifests.sh:")
    print("SERVICES=(")
    for service in sorted(services_with_manifests):
        print(f'    "{service}"')
    print(")")

    if created_dirs:
        print(f"\n⚠️  New directories created that may need .gitkeep or README:")
        for service in sorted(created_dirs):
            print(f"   - src/{service}")

if __name__ == '__main__':
    main()
