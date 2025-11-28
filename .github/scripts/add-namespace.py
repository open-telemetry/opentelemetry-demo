#!/usr/bin/env python3
"""
Script to add namespace to all Kubernetes resources in manifest files.
Usage: ./add-namespace.py <namespace-name>
"""

import yaml
import sys
import os
from pathlib import Path

def add_namespace_to_manifest(file_path, namespace):
    """Add namespace to all resources in a manifest file."""

    # Skip the namespace manifest itself
    if 'demo-namespace-k8s.yaml' in str(file_path):
        print(f"Skipping: {file_path} (namespace definition)")
        return False

    # Skip ServiceAccount (already updated)
    if 'demo-service-account-k8s.yaml' in str(file_path):
        print(f"Skipping: {file_path} (ServiceAccount - already managed)")
        return False

    with open(file_path, 'r') as f:
        content = f.read()

    # Split by document separator
    documents = content.split('\n---\n')

    updated_docs = []
    changed = False

    for doc in documents:
        if not doc.strip():
            continue

        # Check if it's a comment-only section
        if doc.strip().startswith('#') and 'apiVersion' not in doc:
            updated_docs.append(doc)
            continue

        try:
            # Parse YAML
            data = yaml.safe_load(doc)

            if data and isinstance(data, dict) and 'kind' in data:
                # Add namespace if not present
                if 'metadata' in data:
                    if 'namespace' not in data['metadata']:
                        data['metadata']['namespace'] = namespace
                        changed = True
                        print(f"  Adding namespace to {data['kind']}: {data['metadata'].get('name', 'unnamed')}")
                    elif data['metadata']['namespace'] != namespace:
                        # Update existing namespace
                        old_ns = data['metadata']['namespace']
                        data['metadata']['namespace'] = namespace
                        changed = True
                        print(f"  Updating namespace for {data['kind']}: {data['metadata'].get('name', 'unnamed')} ({old_ns} → {namespace})")
                    else:
                        print(f"  Namespace already correct for {data['kind']}: {data['metadata'].get('name', 'unnamed')}")

                # Convert back to YAML
                yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False)
                updated_docs.append(yaml_str.rstrip())
            else:
                # Not a valid K8s resource, keep as-is
                updated_docs.append(doc)
        except Exception as e:
            print(f"  Warning: Could not parse document in {file_path}: {e}")
            updated_docs.append(doc)

    if changed:
        # Reconstruct file with proper separators
        new_content = '---\n'.join(updated_docs)

        # Ensure file ends with newline
        if not new_content.endswith('\n'):
            new_content += '\n'

        with open(file_path, 'w') as f:
            f.write(new_content)

        return True

    return False

def main():
    if len(sys.argv) != 2:
        print("Usage: ./add-namespace.py <namespace-name>")
        sys.exit(1)

    namespace = sys.argv[1]
    print(f"Adding namespace '{namespace}' to all service manifests...\n")

    # Find all *-k8s.yaml files
    src_dir = Path('src')
    manifest_files = sorted(src_dir.glob('*/*-k8s.yaml'))

    updated_count = 0
    skipped_count = 0

    for manifest_file in manifest_files:
        print(f"Processing: {manifest_file}")
        if add_namespace_to_manifest(manifest_file, namespace):
            updated_count += 1
        else:
            skipped_count += 1
        print()

    print("=" * 60)
    print(f"Summary:")
    print(f"  Files updated: {updated_count}")
    print(f"  Files skipped: {skipped_count}")
    print(f"  Total processed: {len(manifest_files)}")

if __name__ == '__main__':
    main()
