# Splunk Astronomy Shop Release Automation

This directory contains scripts and workflows for managing versioned releases of Kubernetes manifests and container images for the Splunk Astronomy Shop.

## Version Tracking

The project uses a centralized `SPLUNK-VERSION` file at the root to track the Splunk-specific version. This version is used for both:
- Combined Kubernetes manifests
- Container image tags

### Current Version

Check the current version:
```bash
cat SPLUNK-VERSION
```

### Bumping Version

Use the `bump-version.sh` script to increment the version:

```bash
# Bump minor version (0.0.0 -> 0.1.0)
.github/scripts/bump-version.sh minor

# Bump major version (0.0.0 -> 1.0.0)
.github/scripts/bump-version.sh major

# Bump patch version (0.0.0 -> 0.0.1)
.github/scripts/bump-version.sh patch
```

## Kubernetes Manifest Stitching

The `stitch-manifests.sh` script combines individual service manifests into a single deployment file.

### How It Works

1. Reads the current version from the `SPLUNK-VERSION` file
2. Looks for `[service]-k8s.yaml` files in each service's `src/` directory
3. Combines all found manifests into `kubernetes/splunk-astronomy-shop-[version].yaml`
4. Reports which services were found and which are missing

### Usage

```bash
# Make the script executable (first time only)
chmod +x .github/scripts/stitch-manifests.sh

# Run the stitching script
.github/scripts/stitch-manifests.sh
```

### Customizing Services

Edit the `SERVICES` array in `stitch-manifests.sh` to add or remove services:

```bash
SERVICES=(
    "accounting"
    "ad"
    "cart"
    # ... add or remove services here
)
```

## GitHub Actions Workflows

### 1. Release Kubernetes Manifests

**Workflow:** `.github/workflows/release-manifests.yml`

Automates the complete release process:
- Bumps the version
- Stitches manifests together
- Commits changes
- Creates a GitHub release
- Uploads manifest as an artifact

**Trigger:** Manual (workflow_dispatch)

**Inputs:**
- `bump_type`: major | minor | patch (default: minor)
- `commit_changes`: Whether to commit and push (default: true)

**To Run:**
1. Go to Actions tab in GitHub
2. Select "Release Kubernetes Manifests"
3. Click "Run workflow"
4. Choose your options and run

### 2. Build and Push Containers

**Workflow:** `.github/workflows/build-containers.yml`

Builds and tags container images with the version from the `SPLUNK-VERSION` file.

**Trigger:** Manual (workflow_dispatch)

**Inputs:**
- `services`: Comma-separated service names or "all" (default: all)
- `use_current_version`: Use SPLUNK-VERSION file as-is (default: true)
- `bump_type`: Version bump if not using current (default: minor)
- `push_to_registry`: Actually push to registry (default: false)

**To Run:**
1. Go to Actions tab in GitHub
2. Select "Build and Push Containers"
3. Click "Run workflow"
4. Configure options:
   - To build all services: leave `services` as "all"
   - To build specific services: enter "cart,checkout,payment"
   - Enable `push_to_registry` when ready to publish

**Container Image Names:**
```
ghcr.io/[org]/[repo]/[service]:[version]
ghcr.io/[org]/[repo]/[service]:latest
```

## Complete Release Process

For a complete release of both manifests and containers:

### Option 1: Sequential (Recommended for first release)

1. **Release Manifests:**
   - Run "Release Kubernetes Manifests" workflow
   - Choose version bump type
   - This will update SPLUNK-VERSION file and create manifest

2. **Build Containers:**
   - Run "Build and Push Containers" workflow
   - Set `use_current_version: true`
   - Set `push_to_registry: true`
   - This will use the version from step 1

### Option 2: Local Testing

Test locally before running in GitHub Actions:

```bash
# Bump version
.github/scripts/bump-version.sh minor

# Stitch manifests
.github/scripts/stitch-manifests.sh

# Review the generated manifest
cat kubernetes/splunk-astronomy-shop-*.yaml

# Commit manually if satisfied
git add SPLUNK-VERSION kubernetes/splunk-astronomy-shop-*.yaml
git commit -m "Release version X.Y.Z"
git push
```

## Creating Service Manifests

For each service that should be included in the stitched manifest:

1. Create a file named `[service-name]-k8s.yaml` in the service directory:
   ```
   src/[service-name]/[service-name]-k8s.yaml
   ```

2. Add your Kubernetes resources (Deployment, Service, ConfigMap, etc.)

3. The manifest will be automatically included in the next release

Example structure:
```
src/
├── cart/
│   ├── cart-k8s.yaml          # Will be included
│   └── ... other files
├── checkout/
│   ├── checkout-k8s.yaml       # Will be included
│   └── ... other files
```

## Maintenance

### Adding New Services

1. Add the service name to the `SERVICES` array in `stitch-manifests.sh`
2. Add the service to the matrix in `build-containers.yml` (if it needs container builds)
3. Create the service's `[service]-k8s.yaml` file

### Removing Services

1. Remove from `SERVICES` array in `stitch-manifests.sh`
2. Remove from matrix in `build-containers.yml`
3. Delete or archive the service's manifest file

## Troubleshooting

### Script Permission Errors

Make scripts executable:
```bash
chmod +x .github/scripts/*.sh
```

### Missing Manifests

The stitch script will warn about missing manifests but continue. Check the output:
```
Warning: Manifest not found for [service] at src/[service]/[service]-k8s.yaml
```

Create the missing manifest files or remove the service from the array.

### Version File Not Found

If `SPLUNK-VERSION` file doesn't exist, the bump script will create it with `0.0.0`.

## Future Enhancements

Consider adding:
- Automated testing of stitched manifests (kubectl dry-run)
- Validation of manifests with kubeval or similar
- Automated changelog generation
- Semantic release automation
- Multi-environment support (dev/staging/prod)
- Rollback capabilities
