#!/usr/bin/env bash
set -euo pipefail

python3 -m pytest oncall/tests -q -m "not live"
