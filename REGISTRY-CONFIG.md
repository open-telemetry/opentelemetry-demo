# Container Registry Configuration

This project supports different container registries for development/test and production environments.

## Configuration

Registry URLs are defined in `services.yaml`:

```yaml
registry:
  # Production registry - used by production workflows
  prod: "ghcr.io/splunk/opentelemetry-demo"

  # Development/Test registry - used by test workflows
  dev: "ghcr.io/hagen-p/opentelemetry-demo-splunk"
```

### Per-Service Registry Control

Individual services can opt out of registry replacement by setting `replace_registry: false`:

```yaml
services:
  - name: my-service
    build: true
    manifest: true
    replace_registry: false  # Keep original registry from k8s.yaml
```

**Use cases:**
- External/third-party containers (e.g., `ghcr.io/splunk/online-boutique/rumloadgen`)
- Services that should always pull from production registry
- Mixed environments with containers from multiple sources

## Usage

### Generate Manifests with Specific Registry

The `stitch-manifests.sh` script accepts an optional registry environment parameter:

```bash
# Use dev registry (replaces all ghcr.io URLs)
.github/scripts/stitch-manifests.sh dev

# Use prod registry
.github/scripts/stitch-manifests.sh prod

# Use original URLs from source manifests (no replacement)
.github/scripts/stitch-manifests.sh
```

### In Workflows

**Test/Development Workflows:**
```yaml
- name: Build test manifest
  run: .github/scripts/stitch-manifests.sh dev
```

**Production Workflows:**
```yaml
- name: Build production manifest
  run: .github/scripts/stitch-manifests.sh prod
```

## How It Works

1. The script reads the registry URL from `services.yaml` based on the environment parameter
2. When adding each service manifest, it replaces all `ghcr.io/*/` registry references with the specified registry
3. The original manifest files remain unchanged - replacement only happens in the generated combined manifest

## Example Output

**With dev registry (replace_registry: true - default):**
```yaml
image: ghcr.io/hagen-p/opentelemetry-demo-splunk:2.1.3
```

**With dev registry (replace_registry: false):**
```yaml
image: ghcr.io/splunk/online-boutique/rumloadgen:5.6  # Original URL preserved
```

**With prod registry:**
```yaml
image: ghcr.io/splunk/opentelemetry-demo:2.1.3
```

**Without registry parameter:**
```yaml
image: ghcr.io/splunk/opentelemetry-demo/otel-ad:2.1.3  # Original from source
```

## Complete Example

```yaml
services:
  # Regular service - registry will be replaced
  - name: frontend
    build: true
    manifest: true
    # replace_registry defaults to true

  # Third-party service - keep original registry
  - name: astronomy-loadgen
    build: false
    manifest: true
    replace_registry: false  # Uses ghcr.io/splunk/online-boutique

  # Production-only service - keep original
  - name: critical-service
    build: false
    manifest: true
    replace_registry: false  # Always uses prod registry
```

## Updating Registry URLs

To change the registry URLs:

1. Edit `services.yaml`
2. Update the `registry.dev` or `registry.prod` values
3. Commit the changes
4. The next manifest generation will use the new URLs
