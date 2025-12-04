# GitHub Environment Setup for Production Builds

## Overview
The production build workflow now uses environment secrets for better security and control. This guide walks you through the one-time setup.

## Step 1: Create Personal Access Token (PAT)

### 1.1 Generate the Token
1. Go to: https://github.com/settings/tokens/new
2. **Token name**: `OpenTelemetry Demo GHCR Access`
3. **Expiration**: Choose your preference (90 days, 1 year, or no expiration)
4. **Select scopes**:
   - ✅ `write:packages` - Upload packages to GitHub Package Registry
   - ✅ `read:packages` - Download packages from GitHub Package Registry
   - ✅ `delete:packages` - Delete packages from GitHub Package Registry (optional)

5. Click **Generate token**
6. **IMPORTANT**: Copy the token immediately - you won't see it again!

Example token format: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Step 2: Create Production Environment

### 2.1 Navigate to Environment Settings
In the **splunk/opentelemetry-demo** repository:

```
Settings → Environments → New environment
```

Or direct link: `https://github.com/splunk/opentelemetry-demo/settings/environments/new`

### 2.2 Configure Environment
**Environment name**: `production`

**Protection rules** (recommended):

#### Required Reviewers (Optional but Recommended)
- Add yourself and/or team members who should approve production deployments
- When enabled, workflow will pause and wait for approval before building images
- Provides audit trail of who approved each build

#### Deployment Branches
- Select: **Selected branches**
- Add rule: `main`
- This ensures only builds from the main branch can use production secrets

#### Wait Timer (Optional)
- Add a delay (e.g., 5 minutes) before deployment starts
- Gives time to cancel if needed

### 2.3 Click "Configure environment"

## Step 3: Add Secret to Environment

### 3.1 Add Environment Secret
In the `production` environment you just created:

1. Scroll to **Environment secrets**
2. Click **Add secret**
3. **Name**: `GHCR_TOKEN`
4. **Value**: Paste your PAT from Step 1
5. Click **Add secret**

## Step 4: Verify Configuration

### 4.1 Check Your Setup
Your environment should now show:
- **Name**: production
- **Secrets**: 1 secret (GHCR_TOKEN)
- **Protection rules**: Your configured rules

### 4.2 Test the Workflow
1. Go to: `Actions → Build Images - PRODUCTION`
2. Click **Run workflow**
3. Configure:
   - Version bump: `patch` (or your choice)
   - Services: `all` or specific service
4. Click **Run workflow**

### Expected Behavior:
If you enabled **Required reviewers**:
1. Workflow starts
2. `determine-version` and `prepare-matrix` jobs complete
3. `build-images` job shows: **"Waiting for approval"**
4. You receive notification to review deployment
5. After approval, build proceeds with GHCR_TOKEN

If no reviewers required:
- Workflow runs automatically with environment secret

## Troubleshooting

### "Environment protection rules not met"
- Check that you're running from the `main` branch
- Verify deployment branch rules in environment settings

### "Secret GHCR_TOKEN not found"
- Verify secret name is exactly `GHCR_TOKEN` (case-sensitive)
- Check it's added to the `production` environment, not repository secrets

### "Permission denied" when pushing images
- Verify PAT has `write:packages` scope
- Check PAT hasn't expired
- Ensure PAT is from a user with write access to splunk org

### "Approval required but no reviewers configured"
- Add yourself as a required reviewer in environment settings
- Or remove the required reviewers protection rule

## Security Benefits

✅ **Token not in repository code** - Stored separately in environment
✅ **Scoped access** - Only production builds can use it
✅ **Manual approval** - Optional review before each deployment
✅ **Audit trail** - GitHub logs who approved deployments
✅ **Easy rotation** - Update token in environment settings
✅ **Branch protection** - Only runs from approved branches

## Token Rotation

When you need to rotate the PAT:

1. Generate new PAT (Step 1)
2. Go to environment secrets: `https://github.com/splunk/opentelemetry-demo/settings/environments/production/edit`
3. Update `GHCR_TOKEN` secret value
4. Old token can be deleted from GitHub settings

No code changes needed!

## Alternative: Organization Secret

For multiple repositories needing the same token:

1. Go to: `https://github.com/organizations/splunk/settings/secrets/actions`
2. Create organization secret: `GHCR_TOKEN`
3. Select repository access: `splunk/opentelemetry-demo`
4. Update workflow to use organization secret

## Summary

You've now configured:
- ✅ Personal Access Token with package write permissions
- ✅ Production environment with protection rules
- ✅ Environment secret (GHCR_TOKEN)
- ✅ Workflow configured to use environment

Next build will require approval and use your secure token!
