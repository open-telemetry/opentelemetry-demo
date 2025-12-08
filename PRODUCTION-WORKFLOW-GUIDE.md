# Production Workflow Guide

## Version Management Updates

The production workflows now support **independent version progression** for both image builds and manifest changes. SPLUNK-VERSION can be bumped in either workflow, allowing you to track manifest changes separately from image builds.

---

## Expected Workflow Outcomes

### Scenario 1: Build All Images with Version Bump

**Action**: Build all services, bump version 1.0.0 → 1.1.0

```yaml
Workflow: prod-build-images.yml
Inputs:
  - services: all
  - version_bump: minor
```

**GitHub Actions Summary:**
```
📊 Current Version State
SPLUNK-VERSION: `1.0.0`

🔼 Version Update
| Type     | Version |
|----------|---------|
| Previous | `1.0.0` |
| New      | `1.1.0` |
| Bump Type| minor   |

📦 Image Versions After Build
Services built this run: `all`

| Service      | Image Version | Status           |
|--------------|---------------|------------------|
| accounting   | `1.1.0`       | ✅ Current (1.1.0) |
| payment      | `1.1.0`       | ✅ Current (1.1.0) |
| cart         | `1.1.0`       | ✅ Current (1.1.0) |
| frontend     | `1.1.0`       | ✅ Current (1.1.0) |
| ...          | ...           | ...              |
```

**Pull Request Created:**
```markdown
## Release 1.1.0

**Version Bump:** minor
**Services:** All services updated

### Changes
- ✅ SPLUNK-VERSION updated to `1.1.0`
- ✅ All hotfixes cleared
- ✅ Source k8s manifests updated with new image references

### Next Steps
Run the **Build Demo Manifest - PRODUCTION** workflow to stitch the manifest.
```

**Files Changed:**
- `SPLUNK-VERSION`: 1.0.0 → 1.1.0
- `src/*/[service]-k8s.yaml`: All updated to reference 1.1.0 images

---

### Scenario 2: Build Single Service (Partial Build with Bump)

**Action**: Build only payment service, bump version 1.1.0 → 1.1.1

```yaml
Workflow: prod-build-images.yml
Inputs:
  - services: payment
  - version_bump: patch
```

**GitHub Actions Summary:**
```
📊 Current Version State
SPLUNK-VERSION: `1.1.0`

🔼 Version Update
| Type     | Version |
|----------|---------|
| Previous | `1.1.0` |
| New      | `1.1.1` |
| Bump Type| patch   |

📦 Image Versions After Build
Services built this run: `payment`

| Service      | Image Version | Status           |
|--------------|---------------|------------------|
| accounting   | `1.1.0`       | ⚠️  Older        |
| payment      | `1.1.1`       | ✅ Current (1.1.1) |
| cart         | `1.1.0`       | ⚠️  Older        |
| frontend     | `1.1.0`       | ⚠️  Older        |
```

**Pull Request Created:**
```markdown
## Production Build: 1.1.1

**Version Bump:** patch
**Services Built:** payment

### Changes
- ✅ SPLUNK-VERSION updated to `1.1.1`
- ✅ Source k8s manifests updated with new image references

### Note
This is a partial build. Other services will use their existing image versions.

### Next Steps
Run the **Build Demo Manifest - PRODUCTION** workflow to stitch the manifest.
```

**Files Changed:**
- `SPLUNK-VERSION`: 1.1.0 → 1.1.1
- `src/payment/payment-k8s.yaml`: Updated to reference 1.1.1 image

---

### Scenario 3: Hotfix Single Service (No Version Bump)

**Action**: Emergency fix for payment service, no version bump

```yaml
Workflow: prod-build-images.yml
Inputs:
  - services: payment
  - version_bump: none (keep current)
```

**GitHub Actions Summary:**
```
📊 Current Version State
SPLUNK-VERSION: `1.1.1`

📦 Image Versions After Build
Services built this run: `payment`

| Service      | Image Version      | Status              |
|--------------|--------------------|---------------------|
| accounting   | `1.1.0`            | ⚠️  Older           |
| payment      | `1.1.1-payment.1`  | 🔧 Hotfix           |
| cart         | `1.1.0`            | ⚠️  Older           |
| frontend     | `1.1.0`            | ⚠️  Older           |
```

**Pull Request Created:**
```markdown
## Hotfix Build: 1.1.1-payment.1

**Service:** payment
**Base Version:** `1.1.1`

### Changes
- ✅ .hotfix.yaml updated
- ✅ Source k8s manifests updated with new image references

### Next Steps
Run the **Build Demo Manifest - PRODUCTION** workflow to stitch the manifest.
```

**Files Changed:**
- `.hotfix.yaml`: Added payment hotfix entry
- `src/payment/payment-k8s.yaml`: Updated to reference 1.1.1-payment.1 image
- `SPLUNK-VERSION`: **Unchanged** (stays 1.1.1)

---

### Scenario 4: Manifest for YAML-Only Changes (No Version Bump)

**Action**: Edit postgres memory limit, create new manifest

**Manual Edit:**
```yaml
# src/postgres/postgres-k8s.yaml
resources:
  limits:
    memory: 1Gi  # Changed from 500Mi
```

**Run Workflow:**
```yaml
Workflow: prod-build-manifest.yml
Inputs:
  - version_bump: none (keep current)
```

**GitHub Actions Summary:**
```
📋 Manifest Version
Version: `1.1.1`

📦 Image Versions in Manifest
This manifest includes the following service image versions:

| Service      | Image Version      | Status              |
|--------------|--------------------|---------------------|
| accounting   | `1.1.0`            | ⚠️  Older           |
| payment      | `1.1.1-payment.1`  | 🔧 Hotfix           |
| cart         | `1.1.0`            | ⚠️  Older           |
| frontend     | `1.1.0`            | ⚠️  Older           |
| postgres     | `latest`           | 📦 External         |

Summary:
Base Version: 1.1.1
Total Services: 25
  - Current (1.1.1): 0
  - Hotfixes: 1
  - Older versions: 20
  - External images: 4
```

**Pull Request Created:**
```markdown
## Production Manifest Update

**Version:** `1.1.1` (unchanged)
**Registry:** Production (`ghcr.io/splunk/opentelemetry-demo`)

### Changes
- ✅ Manifest updated: `kubernetes/splunk-astronomy-shop-1.1.1.yaml`

### Manifest Contents
This manifest combines all service deployments with their current image versions.

See the **Image Versions in Manifest** section in the workflow summary for details.
```

**Files Changed:**
- `kubernetes/splunk-astronomy-shop-1.1.1.yaml`: Recreated with postgres memory change
- `SPLUNK-VERSION`: **Unchanged** (stays 1.1.1)

---

### Scenario 5: Manifest with Version Bump (After YAML Changes)

**Action**: Same postgres change, but bump manifest version 1.1.1 → 1.1.2

**Run Workflow:**
```yaml
Workflow: prod-build-manifest.yml
Inputs:
  - version_bump: patch
```

**GitHub Actions Summary:**
```
📋 Manifest Version
| Type     | Version |
|----------|---------|
| Previous | `1.1.1` |
| New      | `1.1.2` |
| Bump Type| patch   |

📦 Image Versions in Manifest
This manifest includes the following service image versions:

| Service      | Image Version      | Status              |
|--------------|--------------------|---------------------|
| accounting   | `1.1.0`            | ⚠️  Older           |
| payment      | `1.1.1-payment.1`  | 🔧 Hotfix           |
| cart         | `1.1.0`            | ⚠️  Older           |
| frontend     | `1.1.0`            | ⚠️  Older           |
| postgres     | `latest`           | 📦 External         |

Summary:
Base Version: 1.1.2
Total Services: 25
  - Current (1.1.2): 0  ⚠️ No services at current version!
  - Hotfixes: 1
  - Older versions: 20
  - External images: 4
```

**Pull Request Created:**
```markdown
## Production Manifest Release 1.1.2

**Version Bump:** 1.1.1 → 1.1.2 (patch)
**Registry:** Production (`ghcr.io/splunk/opentelemetry-demo`)

### Changes
- ✅ SPLUNK-VERSION updated to `1.1.2`
- ✅ Manifest: `kubernetes/splunk-astronomy-shop-1.1.2.yaml`

### Manifest Contents
This manifest combines all service deployments. It may contain mixed image versions:
- Services built at `1.1.2`  ⚠️ (none in this case)
- Services at older versions
- Hotfixed services with custom versions

See the **Image Versions in Manifest** section in the workflow summary for details.
```

**Files Changed:**
- `SPLUNK-VERSION`: 1.1.1 → 1.1.2
- `kubernetes/splunk-astronomy-shop-1.1.2.yaml`: Created with version 1.1.2

**⚠️ Warning**: The manifest version (1.1.2) doesn't match any built image versions!

---

### Scenario 6: Build Next Service After Manifest Bump

**Action**: Build accounting service after manifest was bumped to 1.1.2

```yaml
Workflow: prod-build-images.yml
Inputs:
  - services: accounting
  - version_bump: patch
```

**Expected Result:**
- Current SPLUNK-VERSION: 1.1.2
- Bumped to: 1.1.3
- Accounting image: 1.1.3

**GitHub Actions Summary:**
```
📊 Current Version State
SPLUNK-VERSION: `1.1.2`

🔼 Version Update
| Type     | Version |
|----------|---------|
| Previous | `1.1.2` |
| New      | `1.1.3` |
| Bump Type| patch   |

📦 Image Versions After Build
Services built this run: `accounting`

| Service      | Image Version      | Status              |
|--------------|--------------------|---------------------|
| accounting   | `1.1.3`            | ✅ Current (1.1.3)  |
| payment      | `1.1.1-payment.1`  | 🔧 Hotfix           |
| cart         | `1.1.0`            | ⚠️  Older           |
| frontend     | `1.1.0`            | ⚠️  Older           |
```

**Files Changed:**
- `SPLUNK-VERSION`: 1.1.2 → 1.1.3
- `src/accounting/accounting-k8s.yaml`: Updated to 1.1.3

---

## Complete Flow Example

**Day 1**: Build all images
```
prod-build-images (all, minor) → 1.0.0 → 1.1.0
prod-build-manifest (none)     → manifest-1.1.0.yaml
```

**Day 2**: Hotfix payment
```
prod-build-images (payment, none) → hotfix: 1.1.0-payment.1
prod-build-manifest (none)         → manifest-1.1.0.yaml (updated)
```

**Day 3**: Edit postgres YAML, bump manifest
```
prod-build-manifest (patch) → 1.1.0 → 1.1.1, manifest-1.1.1.yaml
```

**Day 4**: Build accounting
```
prod-build-images (accounting, patch) → 1.1.1 → 1.1.2
prod-build-manifest (none)            → manifest-1.1.2.yaml
```

**Day 5**: Full release, clear hotfixes
```
prod-build-images (all, minor) → 1.1.2 → 1.2.0, clears hotfixes
prod-build-manifest (none)     → manifest-1.2.0.yaml
```

---

## Version Status Indicators

| Indicator | Meaning |
|-----------|---------|
| ✅ Current | Service is at the base SPLUNK-VERSION |
| 🔧 Hotfix | Service has a hotfix version (e.g., 1.1.0-payment.1) |
| ⚠️ Older | Service is at an older version than SPLUNK-VERSION |
| 🆕 Newer | Service is at a newer version (unusual) |
| 📦 External | Service uses external image (not built by us) |

---

## Best Practices

### When to Bump Versions

**Image Build:**
- ✅ **Full Release** (all services): Use minor or major bump
- ✅ **Partial Build** (few services): Use patch bump
- ✅ **Hotfix** (single service): Use `none` (creates hotfix version)

**Manifest Build:**
- ✅ **After Image Build**: Use `none` (manifest matches image versions)
- ✅ **YAML-Only Changes**: Use patch bump (track configuration changes)
- ⚠️ **Be Careful**: Bumping manifest without images creates version mismatch

### Avoiding Version Confusion

**Good Flow:**
```
Build images (patch)  → 1.1.0 → 1.1.1
Stitch manifest (none) → manifest-1.1.1 (matches images)
```

**Confusing Flow (avoid):**
```
Edit YAML
Stitch manifest (patch) → 1.1.0 → 1.1.1 (no images at 1.1.1!)
Build images (patch)    → 1.1.1 → 1.1.2 (images at 1.1.2, manifest at 1.1.1)
```

### Recommended Strategy

1. **Always build images first** when bumping versions
2. **Stitch manifest with `none`** immediately after image builds
3. **Only bump manifest independently** for YAML-only configuration changes
4. **Review the version breakdown** in GitHub Actions summary before merging PRs

---

## Troubleshooting

### "No services at current version" Warning

This happens when SPLUNK-VERSION was bumped but no services were built at that version.

**Solution**: Either:
- Build at least one service at the current version
- Or revert the version bump and use `none`

### Hotfixes Not Clearing

Hotfixes are only cleared on **full releases** (all services + version bump).

**Solution**: Run a full release build to clear hotfixes:
```yaml
prod-build-images:
  services: all
  version_bump: minor/major
```

### Version Went Backwards

This shouldn't happen with the new workflows, but if it does:

**Solution**: Manually fix SPLUNK-VERSION and run manifest workflow with `none`.

---

## Summary

The updated workflows provide:
- ✅ **Clear version tracking**: Always see current vs new version
- ✅ **Image version breakdown**: Know which services use which versions
- ✅ **Independent progression**: Bump versions for images OR manifests
- ✅ **Visible mixed versions**: GitHub Actions shows exactly what's in each manifest
- ✅ **Better PR messages**: Detailed information about changes

**Container version 1.1.1 and stitched manifest version 1.1.3** is now fully supported and visible!
