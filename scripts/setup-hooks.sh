#!/usr/bin/env bash
# Every teammate runs this ONCE after cloning: bash scripts/setup-hooks.sh
set -euo pipefail
chmod +x scripts/hooks/*
git config core.hooksPath scripts/hooks
echo "✅ Git hooks installed (commits/pushes to main are now blocked locally)."
echo "   Also check your identity: $(git config user.name) <$(git config user.email)>"
