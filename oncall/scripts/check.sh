#!/usr/bin/env bash
set -euo pipefail

python3 -m pytest -q -m "not live"
