#!/bin/bash
# Fork Setup Script
# Run this after forking the splunk/opentelemetry-demo repository

set -e

echo "=========================================="
echo "  OpenTelemetry Demo - Fork Setup"
echo "=========================================="
echo ""

# Check if we're in a git repository
if [ ! -d .git ]; then
    echo "Error: Not a git repository. Run this script from the repository root."
    exit 1
fi

# Check if this is actually a fork (not the main repo)
REPO=$(git remote get-url origin 2>/dev/null || echo "")
if [[ "$REPO" == *"splunk/opentelemetry-demo"* ]] && [[ "$REPO" != *":"*"/"* ]]; then
    echo "⚠️  Warning: This appears to be the main splunk/opentelemetry-demo repository."
    echo "This setup script is intended for forks only."
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 0
    fi
fi

echo "Setting up your fork for development..."
echo ""

# 1. Set up dev-repo.yaml
echo "1. Configuring dev-repo.yaml..."
if [ ! -f dev-repo.yaml ]; then
    if [ -f dev-repo.yaml.example ]; then
        cp dev-repo.yaml.example dev-repo.yaml
        echo "   ✅ Created dev-repo.yaml from example"
        echo "   ⚠️  Please edit dev-repo.yaml with your registry URL:"

        # Try to auto-detect from git remote
        REMOTE_URL=$(git remote get-url origin)
        if [[ "$REMOTE_URL" =~ github\.com[:/]([^/]+)/([^/.]+) ]]; then
            OWNER="${BASH_REMATCH[1]}"
            REPO="${BASH_REMATCH[2]}"
            SUGGESTED_REGISTRY="ghcr.io/${OWNER}/${REPO}"
            echo "   Suggested: $SUGGESTED_REGISTRY"

            # Offer to auto-configure
            read -p "   Auto-configure with this registry? (Y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                cat > dev-repo.yaml << EOF
# Development Registry Configuration (Fork-specific)
# This file is gitignored and won't be committed
registry:
  dev: "$SUGGESTED_REGISTRY"
EOF
                echo "   ✅ Auto-configured dev-repo.yaml"
            fi
        fi
    else
        echo "   ⚠️  dev-repo.yaml.example not found"
    fi
else
    echo "   ✅ dev-repo.yaml already exists"
fi
echo ""

# 2. Add SPLUNK-VERSION to local git exclude
echo "2. Adding SPLUNK-VERSION to local git exclude..."
if grep -q "^SPLUNK-VERSION$" .git/info/exclude 2>/dev/null; then
    echo "   ✅ SPLUNK-VERSION already in .git/info/exclude"
else
    echo "SPLUNK-VERSION" >> .git/info/exclude
    echo "   ✅ Added SPLUNK-VERSION to .git/info/exclude"
fi
echo ""

# 3. Check for .service-versions.yaml
echo "3. Checking .service-versions.yaml..."
if [ ! -f .service-versions.yaml ]; then
    echo "   ⚠️  .service-versions.yaml not found (will be auto-created on first build)"
else
    echo "   ✅ .service-versions.yaml exists"
fi
echo ""

# 4. Summary
echo "=========================================="
echo "  ✅ Fork Setup Complete!"
echo "=========================================="
echo ""
echo "Summary of changes:"
echo "  ✅ dev-repo.yaml configured (fork-specific registry)"
echo "  ✅ SPLUNK-VERSION ignored locally (won't be committed)"
echo "  ✅ Ready for test builds"
echo ""
echo "Next steps:"
echo "  1. Review dev-repo.yaml and update if needed"
echo "  2. Enable GitHub Actions in your fork"
echo "  3. Run 'Build Images - TEST' workflow to build images"
echo "  4. See DEVELOPER.md for complete guide"
echo ""
echo "Important notes:"
echo "  ⚠️  SPLUNK-VERSION is for PRODUCTION use only (main repo)"
echo "  ⚠️  Your fork uses .service-versions.yaml for versioning"
echo "  ⚠️  Don't run PRODUCTION workflows in your fork"
echo ""
