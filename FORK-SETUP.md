# Fork Setup Guide

This guide walks you through forking the Splunk OpenTelemetry Demo repository and configuring it for development.

---

## Forking the Repository

### 1. Create Your Fork

1. Navigate to https://github.com/splunk/opentelemetry-demo
2. Click the **Fork** button in the top-right corner
3. Select your GitHub account as the destination
4. GitHub will create a copy at `https://github.com/YOUR-USERNAME/opentelemetry-demo-splunk`

### 2. Clone Your Fork

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/opentelemetry-demo-splunk.git
cd opentelemetry-demo-splunk

# Add upstream remote to sync with main repo
git remote add upstream https://github.com/splunk/opentelemetry-demo.git

# Verify remotes
git remote -v
```

You should see:
```
origin    https://github.com/YOUR-USERNAME/opentelemetry-demo-splunk.git (fetch)
origin    https://github.com/YOUR-USERNAME/opentelemetry-demo-splunk.git (push)
upstream  https://github.com/splunk/opentelemetry-demo.git (fetch)
upstream  https://github.com/splunk/opentelemetry-demo.git (push)
```

---

## Initial Setup

### Option A: Automated Setup (Recommended)

Run the automated setup script to configure your fork:

```bash
./setup-fork.sh
```

The script will automatically:
- ✅ Create and configure `dev-repo.yaml` with your fork's registry URL
- ✅ Prevent accidental `SPLUNK-VERSION` commits
- ✅ Configure git to ignore production version files locally
- ✅ Verify your fork is ready for test builds

**After running the script, skip to [Step 2: Enable GitHub Actions](#2-enable-github-actions).**

---

### Option B: Manual Setup

If you prefer to configure manually or need to troubleshoot:

#### 1. Configure Your Development Registry

The repository uses GitHub Container Registry (GHCR) for storing container images. You need to configure your fork-specific registry.

**Create `dev-repo.yaml` from the template:**

```bash
# Copy the example file
cp dev-repo.yaml.example dev-repo.yaml
```

**Edit `dev-repo.yaml`** and replace with your GitHub username and repository name:

```yaml
# dev-repo.yaml
registry:
  dev: "ghcr.io/YOUR-USERNAME/opentelemetry-demo-splunk"
```

**Example:**
```yaml
# dev-repo.yaml
registry:
  dev: "ghcr.io/hagen-p/opentelemetry-demo-splunk"
```

> **Important:**
> - `dev-repo.yaml` is gitignored and will NOT be committed to your repository
> - This file is fork-specific and should never be pushed to the main `splunk/opentelemetry-demo` repo
> - Each developer/fork should have their own `dev-repo.yaml`

**Prevent accidental production version commits:**

```bash
# Ignore SPLUNK-VERSION changes locally
git update-index --assume-unchanged SPLUNK-VERSION

# Add to local exclude file
echo "SPLUNK-VERSION" >> .git/info/exclude
```

> **Why this is important:**
> - `SPLUNK-VERSION` is managed by production workflows in the main repository
> - Your fork should NOT modify this file
> - This prevents accidentally overwriting the production version when contributing PRs

---

### 2. Enable GitHub Actions

GitHub Actions workflows are disabled by default in forks. Enable them to use the test build workflows:

1. Go to your fork on GitHub: `https://github.com/YOUR-USERNAME/opentelemetry-demo-splunk`
2. Click the **Actions** tab
3. Click **"I understand my workflows, go ahead and enable them"**

**Workflow Behavior in Forks:**

| Workflow | Runs in Fork | Purpose |
|----------|-------------|---------|
| `test-build-images.yml` | ✅ Yes | Build test images in your fork |
| `test-build-manifest.yml` | ✅ Yes | Create test manifests |
| `prod-build-images.yml` | ❌ No | Production builds (main repo only) |
| `prod-build-manifest.yml` | ❌ No | Production manifests (main repo only) |

> **Note:** Production workflows have repository checks that prevent them from running in forks. This is intentional to prevent accidental production builds.

---

### 3. Configure GitHub Container Registry (GHCR) Permissions

Your fork will push images to GHCR using the built-in `GITHUB_TOKEN`. You just need to ensure proper permissions:

**Enable write permissions for GitHub Actions:**

1. Go to your fork: `https://github.com/YOUR-USERNAME/opentelemetry-demo-splunk`
2. Navigate to **Settings** → **Actions** → **General**
3. Scroll to **Workflow permissions**
4. Select **"Read and write permissions"**
5. Check **"Allow GitHub Actions to create and approve pull requests"** (optional, for automated PRs)
6. Click **Save**

> **Important:**
> - The workflows already include the necessary `permissions:` block to grant `packages: write` access
> - You do **NOT** need to create a Personal Access Token (PAT) for pushing to your own GHCR repository from GitHub Actions
> - The built-in `GITHUB_TOKEN` is sufficient for fork operations
> - Your images will be pushed to: `ghcr.io/YOUR-USERNAME/opentelemetry-demo-splunk`

---

## Verify Your Setup

Run these checks to ensure everything is configured correctly:

### 1. Check dev-repo.yaml

```bash
cat dev-repo.yaml
```

Expected output:
```yaml
registry:
  dev: "ghcr.io/YOUR-USERNAME/opentelemetry-demo-splunk"
```

### 2. Verify SPLUNK-VERSION is ignored

```bash
# Modify SPLUNK-VERSION (test)
echo "9.9.9-test" > SPLUNK-VERSION

# Check git status (should NOT show SPLUNK-VERSION as modified)
git status

# Restore original value
git checkout HEAD -- SPLUNK-VERSION
```

If `SPLUNK-VERSION` does NOT appear in `git status`, configuration is correct.

### 3. Check GitHub Actions is enabled

```bash
# Visit your fork's Actions tab
open https://github.com/YOUR-USERNAME/opentelemetry-demo-splunk/actions
```

You should see a list of workflows.

---

## Test Your Fork

Once setup is complete, test that everything works:

### 1. Run a Test Image Build

1. Go to **Actions** → **"Build Images - TEST"**
2. Click **"Run workflow"**
3. Configure:
   - **Version tag**: `test-1`
   - **Services**: `all`
   - **No cache**: unchecked
4. Click **"Run workflow"**

The workflow will:
- Build all service images
- Tag them as `test-1`
- Push to `ghcr.io/YOUR-USERNAME/opentelemetry-demo-splunk`
- Create `.service-versions.yaml` (auto-generated)
- Update source manifests with new image references
- Create a PR with the changes

### 2. View Your Built Images

After the build completes:

1. Go to your GitHub profile: `https://github.com/YOUR-USERNAME`
2. Click the **Packages** tab
3. You should see packages like:
   - `opentelemetry-demo-splunk/otel-payment`
   - `opentelemetry-demo-splunk/otel-cart`
   - `opentelemetry-demo-splunk/otel-frontend`
   - etc.

---

## Syncing with Upstream

Keep your fork up-to-date with the main repository:

```bash
# Fetch latest changes from upstream
git fetch upstream

# Switch to your main branch
git checkout main

# Merge upstream changes
git merge upstream/main

# Push to your fork
git push origin main
```

**Recommended frequency:** Weekly or before starting new work

---

## Common Issues and Solutions

### Issue: "Permission denied" when pushing images

**Symptom:** Workflow fails with "denied: permission_denied" error

**Solution:**
1. Verify workflow permissions: Settings → Actions → General → Workflow permissions
2. Ensure "Read and write permissions" is selected
3. Re-run the workflow

---

### Issue: dev-repo.yaml not found

**Symptom:** Build workflow fails with "⚠️ dev-repo.yaml not found, using auto-detected registry"

**Solution:**
```bash
# Create from example
cp dev-repo.yaml.example dev-repo.yaml

# Edit with your registry
# Then commit to your fork is NOT needed (file is gitignored)
```

The workflow will auto-detect your registry, but explicitly configuring `dev-repo.yaml` is cleaner.

---

### Issue: SPLUNK-VERSION appears in git status

**Symptom:** `git status` shows SPLUNK-VERSION as modified

**Solution:**
```bash
# Set to assume-unchanged
git update-index --assume-unchanged SPLUNK-VERSION

# Verify it worked (should not show SPLUNK-VERSION)
git status
```

---

### Issue: Production workflows appear in Actions

**Symptom:** You see "Build Images - PRODUCTION" and "Build Demo Manifest - PRODUCTION" workflows

**Expected behavior:** These workflows have repository checks and will immediately skip in forks

**Note:** This is normal. The workflows exist but won't run in your fork due to the `if: github.repository == 'splunk/opentelemetry-demo'` condition.

---

## What's Next?

Your fork is now configured! Here's what you can do:

- **Build test images**: Use "Build Images - TEST" workflow
- **Create test manifests**: Use "Build Demo Manifest - TEST" workflow
- **Make code changes**: Edit services and test in your fork
- **Contribute back**: Submit PRs to the main repository

See [PRODUCTION-WORKFLOW-GUIDE.md](./PRODUCTION-WORKFLOW-GUIDE.md) for detailed workflow documentation.

---

## Contributing Back to Main Repository

When you're ready to contribute your changes:

### DO NOT Include in PRs:
- ❌ `dev-repo.yaml` (fork-specific, gitignored)
- ❌ `SPLUNK-VERSION` (production-only, managed by main repo)
- ❌ `.service-versions.yaml` (test-only, auto-generated)
- ❌ Test manifest files (`kubernetes/TEST-*.yaml`)
- ❌ Generated manifests with your registry URLs

### DO Include in PRs:
- ✅ Source code changes
- ✅ New service implementations
- ✅ Workflow improvements
- ✅ Documentation updates
- ✅ Bug fixes

**PR Validation will automatically check** for these files and provide feedback if they're accidentally included.

---

## Getting Help

If you encounter issues:

1. **Check the Troubleshooting section** above
2. **Re-run the setup script**: `./setup-fork.sh`
3. **Search existing issues**: https://github.com/splunk/opentelemetry-demo/issues
4. **Open a new issue** with:
   - Description of the problem
   - Steps to reproduce
   - Workflow logs (if applicable)
   - Output of `git remote -v` and `cat dev-repo.yaml`

---

## Summary

After completing this guide, your fork will have:

✅ Proper registry configuration (`dev-repo.yaml`)
✅ Protection against accidental production file commits
✅ GitHub Actions enabled and configured
✅ GHCR permissions set up correctly
✅ Test workflows ready to use

You're now ready to develop and test in your fork! 🚀
