#!/usr/bin/env python3
"""
Update source k8s manifest files with newly built image references.
This ensures manifests always reference the last successfully built images.

Usage: python3 update-manifest-images.py <service> <registry> <image_name> <version>
Example: python3 update-manifest-images.py llm ghcr.io/hagen-p/opentelemetry-demo-splunk otel-llm fixing-bug-1
"""

import sys
import re
import os

def update_manifest_image(service, registry, image_name, version):
    """Update the image line in a service's k8s manifest."""
    manifest_path = f"src/{service}/{service}-k8s.yaml"

    if not os.path.exists(manifest_path):
        print(f"Warning: Manifest not found: {manifest_path}")
        return False

    # Read the manifest
    with open(manifest_path, 'r') as f:
        content = f.read()

    # New image reference
    new_image = f"{registry}/{image_name}:{version}"

    # Pattern to match image lines (handles various registry formats)
    # Matches: image: ghcr.io/*/anything:any-tag
    pattern = r'(\s+image:\s+)ghcr\.io/[^\s]+:\S+'

    # Replace with new image
    updated_content, count = re.subn(
        pattern,
        rf'\1{new_image}',
        content
    )

    if count > 0:
        # Write back
        with open(manifest_path, 'w') as f:
            f.write(updated_content)
        print(f"✅ Updated {manifest_path}")
        print(f"   New image: {new_image}")
        return True
    else:
        print(f"⚠️  No image line found in {manifest_path}")
        return False

def main():
    if len(sys.argv) != 5:
        print("Usage: update-manifest-images.py <service> <registry> <image_name> <version>")
        print("Example: update-manifest-images.py llm ghcr.io/hagen-p/opentelemetry-demo-splunk otel-llm fixing-bug-1")
        sys.exit(1)

    service = sys.argv[1]
    registry = sys.argv[2]
    image_name = sys.argv[3]
    version = sys.argv[4]

    print(f"Updating manifest for {service}...")
    success = update_manifest_image(service, registry, image_name, version)

    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
